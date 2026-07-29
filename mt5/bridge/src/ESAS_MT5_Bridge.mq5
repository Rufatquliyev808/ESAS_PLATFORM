#property copyright "ESAS Platform"
#property version   "1.300"
#property strict

#include "../include/EsasTickEvent.mqh"
#include "../include/EsasHttpTransport.mqh"
#include "../include/EsasTickBuffer.mqh"

input bool   InpEmitTickEvents       = true;
input bool   InpSendTicksToBackend   = false;
input string InpBackendTickUrl       = "http://127.0.0.1:8000/events/ticks";
input int    InpHttpTimeoutMs        = 500;
input int    InpTickBufferCapacity   = 1000;
input int    InpRetryIntervalSeconds = 1;
input int    InpRetryBatchSize       = 50;

int OnInit()
{
   if(!g_tick_buffer.Initialize(InpTickBufferCapacity))
   {
      Print(
         "ESAS MT5 Bridge: tick buffer initialization failed",
         " | capacity=", InpTickBufferCapacity
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
      " | buffer_capacity=", g_tick_buffer.Capacity()
   );

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();

   Print(
      "ESAS MT5 Bridge stopped",
      " | reason=", reason,
      " | buffered_events=", g_tick_buffer.Count()
   );
}

void EsasRetryBufferedEvents()
{
   if(!InpSendTicksToBackend ||
      MQLInfoInteger(MQL_TESTER) ||
      g_tick_buffer.IsEmpty())
   {
      return;
   }

   int delivered_count = 0;

   for(int attempt = 0; attempt < InpRetryBatchSize; attempt++)
   {
      string event_json = "";

      if(!g_tick_buffer.Peek(event_json))
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
            " | buffer_count=", g_tick_buffer.Count(),
            " | response=", response_body
         );

         break;
      }

      if(!g_tick_buffer.RemoveFirst())
      {
         Print(
            "ESAS MT5 Bridge: buffered event removal failed",
            " | delivered_in_batch=", delivered_count,
            " | buffer_count=", g_tick_buffer.Count()
         );

         break;
      }

      delivered_count++;
   }

   if(delivered_count > 0)
   {
      Print(
         "ESAS MT5 Bridge: buffered batch delivered",
         " | delivered=", delivered_count,
         " | buffer_count=", g_tick_buffer.Count()
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

   if(!g_tick_buffer.IsEmpty())
   {
      const bool buffered = g_tick_buffer.Enqueue(event_json);

      Print(
         "ESAS MT5 Bridge: event queued behind buffered events",
         " | buffered=", buffered,
         " | buffer_count=", g_tick_buffer.Count(),
         " | buffer_capacity=", g_tick_buffer.Capacity()
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
      const bool buffered = g_tick_buffer.Enqueue(event_json);

      Print(
         "ESAS MT5 Bridge: backend delivery failed",
         " | http_status=", http_status,
         " | error=", transport_error,
         " | buffered=", buffered,
         " | buffer_count=", g_tick_buffer.Count(),
         " | buffer_capacity=", g_tick_buffer.Capacity(),
         " | response=", response_body
      );
   }
}
