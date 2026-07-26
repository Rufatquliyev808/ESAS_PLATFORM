#property copyright "ESAS Platform"
#property version   "1.000"
#property strict

#include "../include/EsasTickEvent.mqh"

input bool InpEmitTickEvents = true;

int OnInit()
{
   Print(
      "ESAS MT5 Bridge started",
      " | module_version=", ESAS_MT5_BRIDGE_MODULE_VERSION,
      " | event_contract=", ESAS_TICK_EVENT_VERSION,
      " | symbol=", _Symbol
   );

   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   Print("ESAS MT5 Bridge stopped | reason=", reason);
}

void OnTick()
{
   if(!InpEmitTickEvents)
      return;

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print("ESAS MT5 Bridge: SymbolInfoTick failed | error=", GetLastError());
      return;
   }

   const EsasTickEvent event = EsasCreateTickEvent(tick);
   Print(EsasSerializeTickEvent(event));
}
