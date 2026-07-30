#property copyright "ESAS Platform"
#property version   "1.400"
#property strict

#include "../include/EsasTickEvent.mqh"
#include "../include/EsasHttpTransport.mqh"
#include "../include/EsasPersistentTickQueue.mqh"

input bool   InpEmitTickEvents       = true;
input bool   InpSendTicksToBackend   = false;
input string InpBackendTickUrl       = "http://127.0.0.1:8000/events/ticks";
input int    InpHttpTimeoutMs        = 500;
input int    InpTickBufferCapacity   = 1000;
input int    InpRetryIntervalSeconds = 1;
input int    InpRetryBatchSize       = 50;

int OnInit()
{
   const string queue_key =
      "ticks_" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LOGIN)) +
      "_" + _Symbol;

   if(!g_tick_queue.Initialize(queue_key, InpTickBufferCapacity))
   {
      Print(
         "ESAS MT5 Bridge: persistent queue initialization failed",
         " | capacity=", InpTickBufferCapacity,
         " | error=", GetLastError()
      );

      return INIT_FAILED;
   }

   if(InpRetryIntervalSeconds <= 0 ||
      InpRetryBatchSize <= 0 ||
      !EventSetTimer(InpRetryIntervalSeconds))
   {
      Print(
         "ESAS MT5 Bridge: retry timer initialization failed",
         " | interval_seconds=", InpRetryIntervalSeconds,
         " | error=", GetLastError()
      );

      return INIT_FAILED;
   }

   Print(
      "ESAS MT5 Bridge started",
      " | module_version=", ESAS_MT5_BRIDGE_MODULE_VERSION,
      " | event_contract=", ESAS_TICK_EVENT_VERSION,
      " | symbol=", _Symbol,
      " | backend_transport=", InpSendTicksToBackend,
      " | queue_count=", g_tick_queue.Count(),
      " | queue_capacity=", g_tick_queue.Capacity(),
      " | queue_file=", g_tick_queue.QueueFile()
   );

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();

   Print(
      "ESAS MT5 Bridge stopped",
      " | reason=", reason,
      " | queued_events=", g_tick_queue.Count()
   );
}

void EsasRetryBufferedEvents()
{
   if(!InpSendTicksToBackend ||
      MQLInfoInteger(MQL_TESTER) ||
      g_tick_queue.IsEmpty())
   {
      return;
   }

   int delivered_count = 0;

   for(int attempt = 0; attempt < InpRetryBatchSize; attempt++)
   {
      string event_json = "";

      if(!g_tick_queue.Peek(event_json))
         break;

      int http_status = 0;
      int transport_error = 0;
      string response_body = "";

      const bool sent = EsasHttpPostJson(
         InpBackendTickUrl,
         event_json,
         InpHttpTimeoutMs,
         http_status,
         response_body,
         transport_error
      );

      if(!sent)
      {
         Print(
            "ESAS MT5 Bridge: buffered event retry failed",
            " | http_status=", http_status,
            " | error=", transport_error,
            " | delivered_in_batch=", delivered_count,
            " | queue_count=", g_tick_queue.Count(),
            " | response=", response_body
         );

         break;
      }

      if(!g_tick_queue.RemoveFirst())
      {
         Print(
            "ESAS MT5 Bridge: persistent event acknowledgement failed",
            " | delivered_in_batch=", delivered_count,
            " | queue_count=", g_tick_queue.Count(),
            " | error=", GetLastError()
         );

         break;
      }

      delivered_count++;
   }

   if(delivered_count > 0)
   {
      Print(
         "ESAS MT5 Bridge: persistent batch delivered",
         " | delivered=", delivered_count,
         " | queue_count=", g_tick_queue.Count()
      );
   }
}

void OnTimer()
{
   EsasRetryBufferedEvents();
}

void OnTick()
{
   if(!InpEmitTickEvents && !InpSendTicksToBackend)
      return;

   MqlTick tick;

   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print(
         "ESAS MT5 Bridge: SymbolInfoTick failed",
         " | error=", GetLastError()
      );

      return;
   }

   const EsasTickEvent event = EsasCreateTickEvent(tick);
   const string event_json = EsasSerializeTickEvent(event);

   if(InpEmitTickEvents)
      Print(event_json);

   if(!InpSendTicksToBackend)
      return;

   // MT5 Strategy Tester daxilində WebRequest işləmir.
   if(MQLInfoInteger(MQL_TESTER))
   {
      static bool tester_warning_printed = false;

      if(!tester_warning_printed)
      {
         Print(
            "ESAS MT5 Bridge: HTTP transport is unavailable ",
            "inside Strategy Tester"
         );

         tester_warning_printed = true;
      }

      return;
   }

   if(!g_tick_queue.IsEmpty())
   {
      const bool queued = g_tick_queue.Enqueue(event_json);

      Print(
         "ESAS MT5 Bridge: event queued behind persistent events",
         " | queued=", queued,
         " | queue_count=", g_tick_queue.Count(),
         " | queue_capacity=", g_tick_queue.Capacity(),
         " | error=", queued ? 0 : GetLastError()
      );

      return;
   }

   int http_status = 0;
   int transport_error = 0;
   string response_body = "";

   const bool sent = EsasHttpPostJson(
      InpBackendTickUrl,
      event_json,
      InpHttpTimeoutMs,
      http_status,
      response_body,
      transport_error
   );

   if(!sent)
   {
      const bool queued = g_tick_queue.Enqueue(event_json);

      Print(
         "ESAS MT5 Bridge: backend delivery failed",
         " | http_status=", http_status,
         " | error=", transport_error,
         " | queued=", queued,
         " | queue_count=", g_tick_queue.Count(),
         " | queue_capacity=", g_tick_queue.Capacity(),
         " | response=", response_body
      );
   }
}
