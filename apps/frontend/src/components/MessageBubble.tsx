import React from 'react';
import { Message } from '../types/Chat';
import { User, Bot, Code, Zap, CheckCircle } from 'lucide-react';

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';
  
  const formatContent = (content: string) => {
    // Handle messages that contain FINAL_ANSWER: anywhere in the content
    if (content.includes('FINAL_ANSWER:')) {
      const parts = content.split('FINAL_ANSWER:');
      const beforePart = parts[0].trim();
      const finalAnswerPart = parts[1].trim();
      
      return (
        <div>
          {beforePart && (
            <>
              {beforePart.startsWith('THOUGHT:') ? (
                <>
                  <div className="thought-message">
                    <Zap size={16} />
                    Thinking...
                  </div>
                  <div className="message-text italic">
                    {beforePart.replace('THOUGHT:', '').trim()}
                  </div>
                </>
              ) : (
                <div className="message-text">
                  {beforePart}
                </div>
              )}
            </>
          )}
          <div className="final-answer-header">
            <CheckCircle size={16} />
            <span>Answer</span>
          </div>
          <div className="final-answer-content">
            {finalAnswerPart}
          </div>
        </div>
      );
    }
    
    if (content.startsWith('THOUGHT:')) {
      return (
        <div>
          <div className="thought-message">
            <Zap size={16} />
            Thinking...
          </div>
          <div className="message-text italic">
            {content.replace('THOUGHT:', '').trim()}
          </div>
        </div>
      );
    }
    
    if (content.startsWith('ACTION_NEEDED:')) {
      return (
        <div>
          <div className="action-message">
            <Code size={16} />
            Taking Action...
          </div>
          <div className="message-text">
            {content.replace('ACTION_NEEDED:', '').trim()}
          </div>
        </div>
      );
    }
    
    if (content.startsWith('FINAL_ANSWER:')) {
      return (
        <div>
          <div className="final-answer-header">
            <CheckCircle size={16} />
            <span>Answer</span>
          </div>
          <div className="final-answer-content">
            {content.replace('FINAL_ANSWER:', '').trim()}
          </div>
        </div>
      );
    }

    if (content.includes('```')) {
      const parts = content.split('```');
      return (
        <div>
          {parts.map((part, index) => {
            if (index % 2 === 1) {
              const lines = part.split('\n');
              const language = lines[0];
              const code = lines.slice(1).join('\n');
              
              return (
                <div key={index} className="code-block">
                  {language && (
                    <div className="code-language">{language}</div>
                  )}
                  <pre className="code-content">
                    <code>{code}</code>
                  </pre>
                </div>
              );
            } else {
              return part.trim() ? (
                <div key={index} className="message-text">
                  {part.trim()}
                </div>
              ) : null;
            }
          })}
        </div>
      );
    }
    
    return <div className="message-text">{content}</div>;
  };

  return (
    <div className={`message-bubble ${isUser ? 'user' : 'assistant'}`}>
      {!isUser && (
        <div className="message-avatar assistant">
          <Bot size={16} />
        </div>
      )}
      
      <div className={`message-content ${isUser ? 'user' : 'assistant'}`}>
        {isUser ? (
          <div className="message-text">{message.content}</div>
        ) : (
          formatContent(message.content)
        )}
        
        {message.isStreaming && (
          <div className="typing-dots">
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
          </div>
        )}
      </div>
      
      {isUser && (
        <div className="message-avatar user">
          <User size={16} />
        </div>
      )}
    </div>
  );
};

export default MessageBubble;