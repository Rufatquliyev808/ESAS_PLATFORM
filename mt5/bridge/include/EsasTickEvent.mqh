#ifndef ESAS_TICK_EVENT_MQH
#define ESAS_TICK_EVENT_MQH

#define ESAS_TICK_EVENT_TYPE              "TICK_RECEIVED"
#define ESAS_TICK_EVENT_VERSION           "1.0"
#define ESAS_MT5_BRIDGE_SOURCE            "esas.mt5.bridge"
#define ESAS_MT5_BRIDGE_MODULE_VERSION "1.3.0"

struct EsasTickEvent
{
   string event_id;
   string event_type;
   string timestamp;
   string source;
   string version;
   string symbol;
   double bid;
   double ask;
   double last;
   ulong  volume;
   uint   flags;
   long   source_time_msc;
   string module_version;
};

string EsasJsonEscape(const string value)
{
   string escaped = value;
   StringReplace(escaped, "\\", "\\\\");
   StringReplace(escaped, "\"", "\\\"");
   StringReplace(escaped, "\r", "\\r");
   StringReplace(escaped, "\n", "\\n");
   StringReplace(escaped, "\t", "\\t");
   return escaped;
}

string EsasUtcTimestamp(const long time_msc)
{
   const datetime seconds = (datetime)(time_msc / 1000);
   const int milliseconds = (int)(time_msc % 1000);

   MqlDateTime parts;
   TimeToStruct(seconds, parts);

   return StringFormat(
      "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ",
      parts.year,
      parts.mon,
      parts.day,
      parts.hour,
      parts.min,
      parts.sec,
      milliseconds
   );
}

string EsasCreateEventId(const string symbol, const long time_msc)
{
   static ulong sequence = 0;
   sequence++;

   return StringFormat(
      "%s:%I64d:%I64u",
      symbol,
      time_msc,
      sequence
   );
}

EsasTickEvent EsasCreateTickEvent(const MqlTick &tick)
{
   EsasTickEvent event;

   event.event_id       = EsasCreateEventId(_Symbol, tick.time_msc);
   event.event_type     = ESAS_TICK_EVENT_TYPE;
   event.timestamp      = EsasUtcTimestamp(tick.time_msc);
   event.source         = ESAS_MT5_BRIDGE_SOURCE;
   event.version        = ESAS_TICK_EVENT_VERSION;
   event.symbol         = _Symbol;
   event.bid            = tick.bid;
   event.ask            = tick.ask;
   event.last           = tick.last;
   event.volume         = tick.volume;
   event.flags          = tick.flags;
   event.source_time_msc = tick.time_msc;
   event.module_version = ESAS_MT5_BRIDGE_MODULE_VERSION;

   return event;
}

string EsasSerializeTickEvent(const EsasTickEvent &event)
{
   const int digits = (int)SymbolInfoInteger(event.symbol, SYMBOL_DIGITS);

   return StringFormat(
      "{\"event_id\":\"%s\",\"event_type\":\"%s\",\"timestamp\":\"%s\","
      "\"source\":\"%s\",\"version\":\"%s\",\"symbol\":\"%s\","
      "\"payload\":{\"bid\":%s,\"ask\":%s,\"last\":%s,"
      "\"volume\":%I64u,\"flags\":%u,\"source_time_msc\":%I64d},"
      "\"metadata\":{\"module_version\":\"%s\"}}",
      EsasJsonEscape(event.event_id),
      EsasJsonEscape(event.event_type),
      EsasJsonEscape(event.timestamp),
      EsasJsonEscape(event.source),
      EsasJsonEscape(event.version),
      EsasJsonEscape(event.symbol),
      DoubleToString(event.bid, digits),
      DoubleToString(event.ask, digits),
      DoubleToString(event.last, digits),
      event.volume,
      event.flags,
      event.source_time_msc,
      EsasJsonEscape(event.module_version)
   );
}

#endif

