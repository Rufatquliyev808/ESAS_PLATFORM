#property copyright "ESAS Platform"
#property version   "1.000"
#property strict

#include "../include/EsasPersistentTickQueue.mqh"

int g_assertions = 0;
int g_failures = 0;

void AssertTrue(const bool condition, const string message)
{
   g_assertions++;

   if(condition)
   {
      Print("ESAS TEST PASS: ", message);
      return;
   }

   g_failures++;
   Print("ESAS TEST FAIL: ", message);
}

string QueuePath(const string key)
{
   return "ESAS_PLATFORM\\queues\\" + key + ".queue";
}

string CheckpointPath(const string key)
{
   return "ESAS_PLATFORM\\queues\\" + key + ".checkpoint";
}

string MetricsPath(const string key)
{
   return "ESAS_PLATFORM\\queues\\" + key + ".metrics";
}

void CleanupTestFiles(const string key)
{
   FileDelete(QueuePath(key), FILE_COMMON);
   FileDelete(CheckpointPath(key), FILE_COMMON);
   FileDelete(MetricsPath(key), FILE_COMMON);
}

void TestPersistentFifo(const string key)
{
   CleanupTestFiles(key);

   EsasPersistentTickQueue first_session;
   AssertTrue(
      first_session.Initialize(key, 2),
      "queue initializes with a valid key and capacity"
   );
   AssertTrue(first_session.Count() == 0, "new queue starts empty");
   AssertTrue(first_session.Enqueue("{\"event_id\":\"first\"}"), "first event is queued");
   AssertTrue(first_session.Enqueue("{\"event_id\":\"second\"}"), "second event is queued");
   AssertTrue(first_session.IsFull(), "queue reports full at capacity");
   AssertTrue(
      !first_session.Enqueue("{\"event_id\":\"rejected\"}"),
      "event beyond capacity is rejected"
   );
   AssertTrue(
      first_session.RejectedEvents() == 1,
      "capacity rejection increments persistent metric"
   );
   AssertTrue(
      first_session.LastError() == ESAS_QUEUE_ERROR_FULL,
      "capacity rejection records queue_full"
   );

   string event_json = "";
   AssertTrue(first_session.Peek(event_json), "first event can be peeked");
   AssertTrue(
      event_json == "{\"event_id\":\"first\"}",
      "FIFO returns the first event"
   );
   AssertTrue(first_session.RemoveFirst(), "peeked event can be acknowledged");
   AssertTrue(first_session.Count() == 1, "acknowledgement removes one event");

   EsasPersistentTickQueue second_session;
   AssertTrue(
      second_session.Initialize(key, 2),
      "queue reinitializes after simulated restart"
   );
   AssertTrue(
      second_session.Count() == 1,
      "pending event is recovered after simulated restart"
   );
   AssertTrue(
      second_session.RejectedEvents() == 1,
      "rejection metric survives simulated restart"
   );

   event_json = "";
   AssertTrue(second_session.Peek(event_json), "recovered event can be peeked");
   AssertTrue(
      event_json == "{\"event_id\":\"second\"}",
      "FIFO order survives simulated restart"
   );
   AssertTrue(second_session.RemoveFirst(), "recovered event can be acknowledged");
   AssertTrue(second_session.IsEmpty(), "queue becomes empty after final acknowledgement");
   AssertTrue(
      !FileIsExist(QueuePath(key), FILE_COMMON),
      "empty queue journal is removed"
   );
   AssertTrue(
      !FileIsExist(CheckpointPath(key), FILE_COMMON),
      "empty queue checkpoint is removed"
   );

   EsasPersistentTickQueue third_session;
   AssertTrue(
      third_session.Initialize(key, 2),
      "empty queue can initialize again"
   );
   AssertTrue(
      third_session.RejectedEvents() == 1,
      "metrics remain available after queue drains"
   );
   AssertTrue(!third_session.Enqueue(""), "empty serialized event is rejected");
   AssertTrue(
      third_session.LastError() == ESAS_QUEUE_ERROR_SERIALIZATION,
      "empty event records serialization error"
   );
   AssertTrue(
      third_session.RejectedEvents() == 2,
      "serialization rejection increments metric"
   );

   CleanupTestFiles(key);
}

void TestCorruptionDetection(const string key)
{
   CleanupTestFiles(key);

   const int handle = FileOpen(
      QueuePath(key),
      FILE_WRITE | FILE_BIN | FILE_COMMON
   );

   AssertTrue(handle != INVALID_HANDLE, "corrupt fixture file can be created");

   if(handle != INVALID_HANDLE)
   {
      FileWriteInteger(handle, 100, INT_VALUE);
      FileFlush(handle);
      FileClose(handle);
   }

   EsasPersistentTickQueue corrupt_queue;
   AssertTrue(
      !corrupt_queue.Initialize(key, 10),
      "truncated queue record is rejected"
   );
   AssertTrue(
      corrupt_queue.LastError() == ESAS_QUEUE_ERROR_CORRUPT,
      "truncated queue records corrupt_queue"
   );

   CleanupTestFiles(key);
}

void TestRetryBatchSemantics(const string key)
{
   CleanupTestFiles(key);

   EsasPersistentTickQueue initial_session;
   AssertTrue(
      initial_session.Initialize(key, 3),
      "retry fixture queue initializes"
   );
   AssertTrue(initial_session.Enqueue("retry-first"), "retry first event is queued");
   AssertTrue(initial_session.Enqueue("retry-second"), "retry second event is queued");
   AssertTrue(initial_session.Enqueue("retry-third"), "retry third event is queued");

   string event_json = "";
   AssertTrue(initial_session.Peek(event_json), "retry attempt can peek first event");
   AssertTrue(event_json == "retry-first", "retry attempt starts with FIFO head");

   // Uğursuz göndəriş RemoveFirst çağırmır. Yeni obyekt EA restartını simulyasiya edir.
   EsasPersistentTickQueue after_failed_delivery;
   AssertTrue(
      after_failed_delivery.Initialize(key, 3),
      "queue reinitializes after simulated failed delivery"
   );
   AssertTrue(
      after_failed_delivery.Count() == 3,
      "failed delivery does not acknowledge or lose an event"
   );
   event_json = "";
   AssertTrue(
      after_failed_delivery.Peek(event_json) && event_json == "retry-first",
      "failed event remains FIFO head for the next retry"
   );

   int delivered = 0;

   for(int attempt = 0; attempt < 2; attempt++)
   {
      event_json = "";

      if(!after_failed_delivery.Peek(event_json))
         break;

      if(!after_failed_delivery.RemoveFirst())
         break;

      delivered++;
   }

   AssertTrue(delivered == 2, "retry cycle respects the simulated batch limit");
   AssertTrue(
      after_failed_delivery.Count() == 1,
      "event beyond the batch limit remains queued"
   );

   EsasPersistentTickQueue after_batch_restart;
   AssertTrue(
      after_batch_restart.Initialize(key, 3),
      "queue reinitializes after a partial retry batch"
   );
   AssertTrue(
      after_batch_restart.Count() == 1,
      "remaining batch event survives simulated restart"
   );
   event_json = "";
   AssertTrue(
      after_batch_restart.Peek(event_json) && event_json == "retry-third",
      "remaining event preserves FIFO order"
   );
   AssertTrue(
      after_batch_restart.RemoveFirst() && after_batch_restart.IsEmpty(),
      "final retry acknowledges the remaining event"
   );

   CleanupTestFiles(key);
}

int OnInit()
{
   const string run_id =
      IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) + "_" +
      IntegerToString((int)GetTickCount());
   const string fifo_key = "test_fifo_" + run_id;
   const string corrupt_key = "test_corrupt_" + run_id;
   const string retry_key = "test_retry_" + run_id;

   TestPersistentFifo(fifo_key);
   TestCorruptionDetection(corrupt_key);
   TestRetryBatchSemantics(retry_key);

   Print(
      "ESAS QUEUE TEST RESULT",
      " | assertions=", g_assertions,
      " | failures=", g_failures,
      " | status=", (g_failures == 0 ? "PASSED" : "FAILED")
   );

   return g_failures == 0 ? INIT_SUCCEEDED : INIT_FAILED;
}

void OnDeinit(const int reason)
{
}
