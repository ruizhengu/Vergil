export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  conversationId: string | null;
}

export interface ApiResponse {
  success: boolean;
  message?: string;
  data?: any;
}