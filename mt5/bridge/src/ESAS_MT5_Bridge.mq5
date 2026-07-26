#property copyright "ESAS Platform"
#property version "1.200"
#property strict

#include "../include/EsasTickEvent.mqh"
#include "../include/EsasHttpTransport.mqh"

input bool   InpEmitTickEvents       = true;
input bool   InpSendTicksToBackend   = false;
input string InpBackendTickUrl       = "http://127.0.0.1:8000/events/ticks";
input int    InpHttpTimeoutMs        = 500;

int OnInit()
{
   Print(
      "ESAS MT5 Bridge started",
      " | module_version=", ESAS_MT5_BRIDGE_MODULE_VERSION,
      " | event_contract=", ESAS_TICK_EVENT_VERSION,
      " | symbol=", _Symbol,
      " | backend_transport=", InpSendTicksToBackend
   );

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Print("ESAS MT5 Bridge stopped | reason=", reason);
}

void OnTick()
{
   if(!InpEmitTickEvents && !InpSendTicksToBackend)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print("ESAS MT5 Bridge: SymbolInfoTick failed | error=", GetLastError());
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
         "ESAS MT5 Bridge: backend delivery failed",
         " | http_status=", http_status,
         " | error=", transport_error,
         " | response=", response_body
      );
   }
}