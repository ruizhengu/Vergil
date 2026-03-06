import React from 'react';
import { Message } from '../types/Chat';
import { User, Bot, Code, Zap, CheckCircle } from 'lucide-react';

interface MessageBubbleProps {
  message: Message;
}

const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user';

  const normalizeContent = (rawContent: string): string => {
    let content = rawContent;

    if (content.startsWith('"') && content.endsWith('"')) {
      try {
        const parsed = JSON.parse(content);
        if (typeof parsed === 'string') {
          content = parsed;
        }
      } catch {
      }
    }

    if (!content.includes('\n') && content.includes('\\n')) {
      content = content.replace(/\\n/g, '\n');
    }

    // Convert escaped triple backticks to actual triple backticks
    if (!content.includes('```') && content.includes('\\`\\`\\`')) {
      content = content.replace(/\\`/g, '`');
    }

    // Convert single backticks to triple backticks for code blocks
    // This handles patterns like `solidity code here` where the code starts with a language name
    if (!content.includes('```') && content.includes('`')) {
      // Replace single backticks with triple backticks around code-like content
      content = content.replace(/`(\w+\s+[\w\W]*?\w+)`/g, '```$1```');
    }

    if (content.includes('\\"')) {
      content = content.replace(/\\"/g, '"');
    }

    return content;
  };

  // Helper function to format content with code blocks
  const formatContent = (rawContent: string): React.ReactNode => {
    const content = normalizeContent(rawContent);

    // Check if content has code blocks first
    if (content.includes('```')) {
      const parts = content.split('```');
      const elements: React.ReactNode[] = [];

      for (let i = 0; i < parts.length; i++) {
        if (i % 2 === 0) {
          // Regular text part
          const text = parts[i];
          if (text.trim()) {
            // Check for FINAL_ANSWER prefix
            let textContent = text.trim();
            let showFinalAnswer = false;
            let finalAnswerContent = '';

            if (textContent.startsWith('FINAL_ANSWER:')) {
              showFinalAnswer = true;
              finalAnswerContent = textContent.replace('FINAL_ANSWER:', '').trim();
            }

            if (showFinalAnswer && finalAnswerContent) {
              elements.push(
                <div key={`final-${i}`} className="final-answer-content">
                  {finalAnswerContent}
                </div>
              );
            } else if (textContent) {
              elements.push(
                <div key={`text-${i}`} className="message-text">
                  {textContent}
                </div>
              );
            }
          }
        } else {
          // Code block part
          let codeContent = parts[i];
          let language = 'code';

          // Extract language if present
          const firstNewlineIndex = codeContent.indexOf('\n');
          if (firstNewlineIndex !== -1 && firstNewlineIndex < 20) {
            const potentialLang = codeContent.slice(0, firstNewlineIndex).trim();
            if (/^[a-zA-Z0-9]+$/.test(potentialLang)) {
              language = potentialLang;
              codeContent = codeContent.slice(firstNewlineIndex + 1);
            }
          }

          elements.push(
            <div key={`code-${i}`} className="code-block">
              <div className="code-language">{language.toUpperCase()}</div>
              <pre className="code-content">
                <code>{codeContent.trim()}</code>
              </pre>
            </div>
          );
        }
      }

      return elements.length > 0 ? <div>{elements}</div> : <div className="message-text">{content}</div>;
    }

    // Check for FINAL_ANSWER format
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

    // Check for THOUGHT format
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

    // Check for ACTION_NEEDED format
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

    // Default: just return the content as text
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
