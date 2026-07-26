#ifndef ESAS_HTTP_TRANSPORT_MQH
#define ESAS_HTTP_TRANSPORT_MQH

bool EsasHttpPostJson(
   const string url,
   const string json,
   const int timeout_ms,
   int &http_status,
   string &response_body,
   int &transport_error
)
{
   char request_body[];
   char response_data[];
   string response_headers;

   StringToCharArray(json, request_body, 0, WHOLE_ARRAY, CP_UTF8);

   // StringToCharArray sonuna NULL simvolu əlavə edir.
   // HTTP body daxilində həmin simvol göndərilməməlidir.
   const int request_size = ArraySize(request_body);
   if(request_size > 0)
      ArrayResize(request_body, request_size - 1);

   ResetLastError();

   http_status = WebRequest(
      "POST",
      url,
      "Content-Type: application/json\r\n",
      timeout_ms,
      request_body,
      response_data,
      response_headers
   );

   transport_error = GetLastError();
   response_body = CharArrayToString(response_data, 0, WHOLE_ARRAY, CP_UTF8);

   return http_status >= 200 && http_status < 300;
}

#endif