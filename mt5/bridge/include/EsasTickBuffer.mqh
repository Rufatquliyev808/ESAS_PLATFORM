#ifndef ESAS_TICK_BUFFER_MQH
#define ESAS_TICK_BUFFER_MQH

class EsasTickBuffer
{
private:
   string m_items[];
   int    m_capacity;
   int    m_head;
   int    m_count;

public:
   EsasTickBuffer(void)
   {
      m_capacity = 0;
      m_head     = 0;
      m_count    = 0;
   }

   bool Initialize(const int capacity)
   {
      if(capacity <= 0)
         return false;

      ArrayFree(m_items);

      const int resized_size = ArrayResize(m_items, capacity);

      if(resized_size != capacity)
      {
         m_capacity = 0;
         m_head     = 0;
         m_count    = 0;
         return false;
      }

      m_capacity = capacity;
      m_head     = 0;
      m_count    = 0;

      return true;
   }

   void Clear(void)
   {
      for(int i = 0; i < m_capacity; i++)
         m_items[i] = "";

      m_head  = 0;
      m_count = 0;
   }

   int Count(void) const
   {
      return m_count;
   }

   int Capacity(void) const
   {
      return m_capacity;
   }

   bool IsInitialized(void) const
   {
      return m_capacity > 0;
   }

   bool IsEmpty(void) const
   {
      return m_count == 0;
   }

   bool IsFull(void) const
   {
      return m_capacity > 0 && m_count >= m_capacity;
   }

   bool Enqueue(const string event_json)
   {
      if(!IsInitialized() || IsFull())
         return false;

      const int index = (m_head + m_count) % m_capacity;

      m_items[index] = event_json;
      m_count++;

      return true;
   }

   bool Peek(string &event_json) const
   {
      if(IsEmpty())
         return false;

      event_json = m_items[m_head];
      return true;
   }

   bool RemoveFirst(void)
   {
      if(IsEmpty())
         return false;

      m_items[m_head] = "";
      m_head = (m_head + 1) % m_capacity;
      m_count--;

      return true;
   }
};

// ESAS MT5 Bridge tərəfindən istifadə edilən vahid FIFO buffer obyekti.
EsasTickBuffer g_tick_buffer;

#endif