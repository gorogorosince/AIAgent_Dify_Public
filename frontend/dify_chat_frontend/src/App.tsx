import { useState, useEffect } from 'react'
import './App.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: string
}

interface ChatResponse {
  conversation_id: string
  message: string
  timestamp: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)

  useEffect(() => {
    fetchChatHistory()
  }, [])

  const fetchChatHistory = async () => {
    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/chat/history`)
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const data = await response.json()
      if (!Array.isArray(data)) {
        console.error('Expected array response from server, got:', data)
        return
      }
      // Sort messages by timestamp in ascending order
      const sortedData = [...data].sort((a, b) => 
        new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
      
      const formattedMessages: Message[] = sortedData.map((msg: any) => ([
        {
          role: 'user' as const,
          content: msg.user_message,
          timestamp: msg.timestamp
        },
        {
          role: 'assistant' as const,
          content: msg.assistant_message,
          timestamp: msg.timestamp
        }
      ])).flat()
      
      setMessages(formattedMessages)
      if (sortedData.length > 0) {
        // Use the conversation_id from the most recent message
        setConversationId(sortedData[sortedData.length - 1].conversation_id)
      }
    } catch (error) {
      console.error('Error fetching chat history:', error)
    }
  }

  const sendMessage = async () => {
    if (!input.trim()) return

    const userMessage: Message = {
      role: 'user',
      content: input,
      timestamp: new Date().toISOString()
    }

    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)

    try {
      const response = await fetch(`${import.meta.env.VITE_API_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          conversation_id: conversationId
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data: ChatResponse = await response.json()
      if (!data.message || !data.conversation_id) {
        throw new Error('Invalid response format from server')
      }
      setConversationId(data.conversation_id)
      
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.message,
        timestamp: data.timestamp
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      console.error('Error sending message:', error)
      const errorMessage: Message = {
        role: 'assistant',
        content: 'メッセージの送信中にエラーが発生しました。もう一度お試しください。',
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="container mx-auto p-6">
        <div className="max-w-4xl mx-auto bg-white rounded-2xl shadow-lg">
          <div className="h-screen max-h-96 overflow-y-auto p-8 space-y-8 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`p-4 rounded-2xl max-w-[80%] shadow-sm ${
                  message.role === 'user'
                    ? 'bg-gray-50 text-gray-700'
                    : 'bg-gray-100 text-gray-700'
                }`}>
                  <p className="leading-relaxed whitespace-pre-wrap">{message.content}</p>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 p-4 rounded-2xl max-w-[80%] text-gray-700 shadow-sm">
                  <p className="flex items-center">
                    <span className="mr-2">応答を生成中</span>
                    <span className="animate-pulse text-gray-500">...</span>
                  </p>
                </div>
              </div>
            )}
          </div>
          <div className="p-6 border-t border-gray-600">
            <div className="flex gap-3">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                placeholder="メッセージを入力..."
                className="flex-1 p-3 bg-gray-50 text-gray-700 border border-gray-200 rounded-2xl focus:outline-none focus:ring-2 focus:ring-gray-300 focus:border-transparent placeholder-gray-400"
                disabled={isLoading}
              />
              <button
                onClick={sendMessage}
                disabled={isLoading}
                className="px-6 py-3 bg-gray-700 text-white rounded-2xl hover:bg-gray-800 disabled:opacity-50 transition-colors duration-200 font-medium shadow-sm"
              >
                送信
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
