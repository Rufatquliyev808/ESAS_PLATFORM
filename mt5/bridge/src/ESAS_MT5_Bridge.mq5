#property copyright "ESAS Platform"
#property version   "1.600"
#property strict

#include "../include/EsasTickEvent.mqh"
#include "../include/EsasHttpTransport.mqh"
#include "../include/EsasPersistentTickQueue.mqh"

input bool   InpEmitTickEvents       = true;
input bool   InpSendTicksToBackend   = false;
input string InpBackendTickUrl       = "http://127.0.0.1:8000/events/ticks";
input string InpBackendStatusUrl     = "http://127.0.0.1:8000/status/bridge";
input string InpBackendBridgeKey     = "";
input int    InpHttpTimeoutMs        = 500;
input int    InpTickBufferCapacity   = 1000;
input int    InpRetryIntervalSeconds = 1;
input int    InpRetryBatchSize       = 50;
input int    InpStatusIntervalSeconds = 5;

int OnInit()
{
   if(InpSendTicksToBackend &&
      (StringLen(InpBackendBridgeKey) < 32 ||
       StringFind(InpBackendBridgeKey, "\r") >= 0 ||
       StringFind(InpBackendBridgeKey, "\n") >= 0))
   {
      Print(
         "ESAS MT5 Bridge: backend bridge key is missing or invalid",
         " | minimum_length=32"
      );
      return INIT_FAILED;
   }

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
      InpStatusIntervalSeconds <= 0 ||
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

void EsasReportBridgeStatus()
{
   if(!InpSendTicksToBackend || MQLInfoInteger(MQL_TESTER))
      return;

   static datetime last_reported_at = 0;
   const datetime current_time = TimeLocal();

   if(last_reported_at > 0 &&
      current_time - last_reported_at < InpStatusIntervalSeconds)
   {
      return;
   }

   last_reported_at = current_time;

   string queue_status = "healthy";

   if(g_tick_queue.IsFull())
      queue_status = "full";
   else if(g_tick_queue.RejectedEvents() > 0)
      queue_status = "degraded";
   else if(!g_tick_queue.IsEmpty())
      queue_status = "backlogged";

   const string status_json =
      "{" +
      "\"source\":\"esas.mt5.bridge\"," +
      "\"module_version\":\"" + ESAS_MT5_BRIDGE_MODULE_VERSION + "\"," +
      "\"symbol\":\"" + EsasJsonEscape(_Symbol) + "\"," +
      "\"queue_status\":\"" + queue_status + "\"," +
      "\"queue_count\":" + IntegerToString(g_tick_queue.Count()) + "," +
      "\"queue_capacity\":" + IntegerToString(g_tick_queue.Capacity()) + "," +
      "\"rejected_events\":" +
         (string)g_tick_queue.RejectedEvents() + "," +
      "\"last_queue_error\":\"" + g_tick_queue.LastErrorName() + "\"" +
      "}";

   int http_status = 0;
   int transport_error = 0;
   string response_body = "";

   const bool sent = EsasHttpPostJson(
      InpBackendStatusUrl,
      status_json,
      InpBackendBridgeKey,
      InpHttpTimeoutMs,
      http_status,
      response_body,
      transport_error
   );

   if(!sent)
   {
      Print(
         "ESAS MT5 Bridge: status delivery failed",
         " | http_status=", http_status,
         " | error=", transport_error,
         " | queue_status=", queue_status,
         " | rejected_events=", g_tick_queue.RejectedEvents()
      );
   }
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
         InpBackendBridgeKey,
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
   EsasReportBridgeStatus();
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
         " | queue_error=", g_tick_queue.LastErrorName(),
         " | rejected_events=", g_tick_queue.RejectedEvents()
      );

      return;
   }

   int http_status = 0;
   int transport_error = 0;
   string response_body = "";

   const bool sent = EsasHttpPostJson(
      InpBackendTickUrl,
      event_json,
      InpBackendBridgeKey,
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
         " | queue_error=", g_tick_queue.LastErrorName(),
         " | rejected_events=", g_tick_queue.RejectedEvents(),
         " | response=", response_body
      );
   }
}
