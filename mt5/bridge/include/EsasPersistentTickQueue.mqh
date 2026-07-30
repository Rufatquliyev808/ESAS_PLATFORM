#ifndef ESAS_PERSISTENT_TICK_QUEUE_MQH
#define ESAS_PERSISTENT_TICK_QUEUE_MQH

enum EsasQueueError
{
   ESAS_QUEUE_ERROR_NONE = 0,
   ESAS_QUEUE_ERROR_FULL = 1,
   ESAS_QUEUE_ERROR_SERIALIZATION = 2,
   ESAS_QUEUE_ERROR_DISK_OPEN = 3,
   ESAS_QUEUE_ERROR_DISK_SEEK = 4,
   ESAS_QUEUE_ERROR_DISK_WRITE = 5,
   ESAS_QUEUE_ERROR_CORRUPT = 6
};

class EsasPersistentTickQueue
{
private:
   string m_queue_file;
   string m_checkpoint_file;
   string m_metrics_file;
   int    m_capacity;
   int    m_count;
   long   m_rejected_events;
   EsasQueueError m_last_error;
   long   m_read_offset;
   long   m_next_offset;
   bool   m_peek_ready;

   void PersistMetrics(void)
   {
      const int handle = FileOpen(
         m_metrics_file,
         FILE_WRITE | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
         return;

      FileWriteLong(handle, m_rejected_events);
      FileWriteInteger(handle, (int)m_last_error, INT_VALUE);
      FileFlush(handle);
      FileClose(handle);
   }

   void Reject(const EsasQueueError error)
   {
      m_last_error = error;
      m_rejected_events++;
      PersistMetrics();
   }

   void ReadMetrics(void)
   {
      m_rejected_events = 0;
      m_last_error = ESAS_QUEUE_ERROR_NONE;

      if(!FileIsExist(m_metrics_file, FILE_COMMON))
         return;

      const int handle = FileOpen(
         m_metrics_file,
         FILE_READ | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
         return;

      if(FileSize(handle) >= 12)
      {
         m_rejected_events = FileReadLong(handle);
         m_last_error = (EsasQueueError)FileReadInteger(
            handle,
            INT_VALUE
         );
      }

      FileClose(handle);

      if(m_rejected_events < 0)
         m_rejected_events = 0;
   }

   bool ReadCheckpoint(long &offset)
   {
      offset = 0;

      if(!FileIsExist(m_checkpoint_file, FILE_COMMON))
         return true;

      const int handle = FileOpen(
         m_checkpoint_file,
         FILE_READ | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
         return false;

      if(FileSize(handle) >= 8)
         offset = FileReadLong(handle);

      FileClose(handle);

      if(offset < 0)
         offset = 0;

      return true;
   }

   bool WriteCheckpoint(const long offset)
   {
      const int handle = FileOpen(
         m_checkpoint_file,
         FILE_WRITE | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
         return false;

      FileWriteLong(handle, offset);
      FileFlush(handle);
      FileClose(handle);
      return true;
   }

   bool ReadRecord(
      const int handle,
      const long offset,
      string &event_json,
      long &next_offset
   )
   {
      event_json = "";
      next_offset = offset;
      const long file_size = (long)FileSize(handle);

      if(offset < 0 || offset + 4 > file_size)
         return false;

      if(!FileSeek(handle, offset, SEEK_SET))
         return false;

      const int payload_size = FileReadInteger(handle, INT_VALUE);

      if(payload_size <= 0 || offset + 4 + payload_size > file_size)
         return false;

      uchar payload[];

      if(ArrayResize(payload, payload_size) != payload_size)
         return false;

      const uint bytes_read = FileReadArray(
         handle,
         payload,
         0,
         payload_size
      );

      if((int)bytes_read != payload_size)
         return false;

      event_json = CharArrayToString(payload, 0, payload_size, CP_UTF8);
      next_offset = (long)FileTell(handle);
      return event_json != "";
   }

   bool RebuildCount(void)
   {
      m_count = 0;

      if(!FileIsExist(m_queue_file, FILE_COMMON))
      {
         m_read_offset = 0;
         return true;
      }

      const int handle = FileOpen(
         m_queue_file,
         FILE_READ | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
         return false;

      const long file_size = (long)FileSize(handle);

      if(m_read_offset > file_size)
         m_read_offset = 0;

      long offset = m_read_offset;

      while(offset < file_size)
      {
         string event_json = "";
         long next_offset = offset;

         if(!ReadRecord(handle, offset, event_json, next_offset))
         {
            m_last_error = ESAS_QUEUE_ERROR_CORRUPT;
            FileClose(handle);
            return false;
         }

         offset = next_offset;
         m_count++;
      }

      FileClose(handle);
      return offset == file_size;
   }

   void CleanupIfEmpty(void)
   {
      if(m_count != 0)
         return;

      FileDelete(m_queue_file, FILE_COMMON);
      FileDelete(m_checkpoint_file, FILE_COMMON);
      m_read_offset = 0;
      m_next_offset = 0;
      m_peek_ready = false;
   }

public:
   EsasPersistentTickQueue(void)
   {
      m_queue_file = "";
      m_checkpoint_file = "";
      m_metrics_file = "";
      m_capacity = 0;
      m_count = 0;
      m_rejected_events = 0;
      m_last_error = ESAS_QUEUE_ERROR_NONE;
      m_read_offset = 0;
      m_next_offset = 0;
      m_peek_ready = false;
   }

   bool Initialize(const string queue_key, const int capacity)
   {
      if(queue_key == "" || capacity <= 0)
         return false;

      m_queue_file = "ESAS_PLATFORM\\queues\\" + queue_key + ".queue";
      m_checkpoint_file =
         "ESAS_PLATFORM\\queues\\" + queue_key + ".checkpoint";
      m_metrics_file = "ESAS_PLATFORM\\queues\\" + queue_key + ".metrics";
      m_capacity = capacity;
      m_count = 0;
      m_rejected_events = 0;
      m_last_error = ESAS_QUEUE_ERROR_NONE;
      m_read_offset = 0;
      m_next_offset = 0;
      m_peek_ready = false;

      ReadMetrics();

      if(!ReadCheckpoint(m_read_offset))
      {
         m_last_error = ESAS_QUEUE_ERROR_DISK_OPEN;
         return false;
      }

      if(!RebuildCount())
      {
         PersistMetrics();
         return false;
      }

      CleanupIfEmpty();
      return true;
   }

   int Count(void) const
   {
      return m_count;
   }

   int Capacity(void) const
   {
      return m_capacity;
   }

   bool IsEmpty(void) const
   {
      return m_count == 0;
   }

   bool IsFull(void) const
   {
      return m_capacity > 0 && m_count >= m_capacity;
   }

   string QueueFile(void) const
   {
      return m_queue_file;
   }

   long RejectedEvents(void) const
   {
      return m_rejected_events;
   }

   EsasQueueError LastError(void) const
   {
      return m_last_error;
   }

   string LastErrorName(void) const
   {
      switch(m_last_error)
      {
         case ESAS_QUEUE_ERROR_FULL:
            return "queue_full";
         case ESAS_QUEUE_ERROR_SERIALIZATION:
            return "serialization_failed";
         case ESAS_QUEUE_ERROR_DISK_OPEN:
            return "disk_open_failed";
         case ESAS_QUEUE_ERROR_DISK_SEEK:
            return "disk_seek_failed";
         case ESAS_QUEUE_ERROR_DISK_WRITE:
            return "disk_write_failed";
         case ESAS_QUEUE_ERROR_CORRUPT:
            return "corrupt_queue";
      }

      return "none";
   }

   bool Enqueue(const string event_json)
   {
      if(event_json == "" || m_capacity <= 0)
      {
         Reject(ESAS_QUEUE_ERROR_SERIALIZATION);
         return false;
      }

      if(IsFull())
      {
         Reject(ESAS_QUEUE_ERROR_FULL);
         return false;
      }

      uchar payload[];
      int payload_size = StringToCharArray(
         event_json,
         payload,
         0,
         WHOLE_ARRAY,
         CP_UTF8
      );

      if(payload_size <= 1)
      {
         Reject(ESAS_QUEUE_ERROR_SERIALIZATION);
         return false;
      }

      payload_size--;

      const int handle = FileOpen(
         m_queue_file,
         FILE_READ | FILE_WRITE | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
      {
         Reject(ESAS_QUEUE_ERROR_DISK_OPEN);
         return false;
      }

      if(!FileSeek(handle, 0, SEEK_END))
      {
         FileClose(handle);
         Reject(ESAS_QUEUE_ERROR_DISK_SEEK);
         return false;
      }

      FileWriteInteger(handle, payload_size, INT_VALUE);
      const uint bytes_written = FileWriteArray(
         handle,
         payload,
         0,
         payload_size
      );
      FileFlush(handle);
      FileClose(handle);

      if((int)bytes_written != payload_size)
      {
         Reject(ESAS_QUEUE_ERROR_DISK_WRITE);
         return false;
      }

      m_count++;
      return true;
   }

   bool Peek(string &event_json)
   {
      if(IsEmpty())
         return false;

      const int handle = FileOpen(
         m_queue_file,
         FILE_READ | FILE_BIN | FILE_COMMON
      );

      if(handle == INVALID_HANDLE)
         return false;

      const bool result = ReadRecord(
         handle,
         m_read_offset,
         event_json,
         m_next_offset
      );

      FileClose(handle);
      m_peek_ready = result;
      return result;
   }

   bool RemoveFirst(void)
   {
      if(IsEmpty() || !m_peek_ready || m_next_offset <= m_read_offset)
         return false;

      if(!WriteCheckpoint(m_next_offset))
         return false;

      m_read_offset = m_next_offset;
      m_count--;
      m_peek_ready = false;
      CleanupIfEmpty();
      return true;
   }
};

EsasPersistentTickQueue g_tick_queue;

#endif
