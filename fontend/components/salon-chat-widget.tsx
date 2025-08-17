"use client";

import type React from "react";

import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Send,
  X,
  Minimize2,
  Maximize2,
  Minimize,
  Scissors,
} from "lucide-react";

interface Message {
  id: string;
  content: string;
  sender: "user" | "bot";
  timestamp: Date;
}

type ChatSize = "small" | "medium" | "large" | "custom";

export function SalonChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [chatSize, setChatSize] = useState<ChatSize>("medium");
  const [customDimensions, setCustomDimensions] = useState({
    width: 320,
    height: 384,
  });
  const [isResizing, setIsResizing] = useState(false);
  const [resizeStart, setResizeStart] = useState({
    x: 0,
    y: 0,
    width: 0,
    height: 0,
  });
  const chatRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [userId] = useState(
    () => `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
  );

  const getSizeClasses = (size: ChatSize) => {
    if (isResizing || size === "custom") {
      return "";
    }
    switch (size) {
      case "small":
        return "w-72 h-80";
      case "medium":
        return "w-80 h-96";
      case "large":
        return "w-96 h-[32rem]";
      default:
        return "w-80 h-96";
    }
  };

  const toggleSize = () => {
    setChatSize((prev) => {
      let newSize: ChatSize;
      switch (prev) {
        case "small":
          newSize = "medium";
          setCustomDimensions({ width: 320, height: 384 });
          break;
        case "medium":
          newSize = "large";
          setCustomDimensions({ width: 384, height: 512 });
          break;
        case "large":
          newSize = "small";
          setCustomDimensions({ width: 288, height: 320 });
          break;
        default:
          newSize = "medium";
          setCustomDimensions({ width: 320, height: 384 });
      }
      return newSize;
    });
  };

  const handleResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    setChatSize("custom");
    setResizeStart({
      x: e.clientX,
      y: e.clientY,
      width: customDimensions.width,
      height: customDimensions.height,
    });
  };

  const handleResizeMove = (e: MouseEvent) => {
    if (!isResizing) return;

    const deltaX = e.clientX - resizeStart.x;
    const deltaY = resizeStart.y - e.clientY;

    const newWidth = Math.max(250, Math.min(600, resizeStart.width + deltaX));
    const newHeight = Math.max(300, Math.min(700, resizeStart.height + deltaY));

    setCustomDimensions({ width: newWidth, height: newHeight });
  };

  const handleResizeEnd = () => {
    setIsResizing(false);
  };

  useEffect(() => {
    if (isResizing) {
      document.addEventListener("mousemove", handleResizeMove);
      document.addEventListener("mouseup", handleResizeEnd);
      document.body.style.cursor = "nw-resize";
      document.body.style.userSelect = "none";

      return () => {
        document.removeEventListener("mousemove", handleResizeMove);
        document.removeEventListener("mouseup", handleResizeEnd);
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      };
    }
  }, [isResizing, resizeStart]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      content: inputValue,
      sender: "user",
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setIsLoading(true);
    setIsTyping(true);

    try {
      const payload = {
        message: inputValue,
        userId: userId,
      };

      await new Promise((resolve) => setTimeout(resolve, 800));

      const response = await fetch("/api/chat", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.reply) {
        setTimeout(() => {
          const botMessage: Message = {
            id: (Date.now() + 1).toString(),
            content: data.reply,
            sender: "bot",
            timestamp: new Date(),
          };

          setMessages((prev) => [...prev, botMessage]);
          setIsTyping(false);
        }, 500);
      } else {
        setIsTyping(false);
      }
    } catch (error) {
      setIsTyping(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {/* Chat Button */}
      {!isOpen && (
        <Button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full bg-pink-600 hover:bg-pink-700 shadow-lg hover:shadow-xl transition-all duration-300 z-50 hover:scale-110 animate-bounce"
          size="icon"
        >
          <Scissors className="w-6 h-6 text-white transition-transform duration-200 hover:rotate-12" />
        </Button>
      )}

      {/* Chat Window */}
      {isOpen && (
        <div
          ref={chatRef}
          className={`fixed bottom-6 right-6 ${getSizeClasses(
            chatSize
          )} bg-white rounded-lg shadow-2xl border border-gray-200 flex flex-col z-50 transition-all duration-500 ease-out animate-in slide-in-from-bottom-4 slide-in-from-right-4 fade-in ${
            isResizing ? "select-none" : ""
          }`}
          style={
            chatSize === "custom" || isResizing
              ? {
                  width: `${customDimensions.width}px`,
                  height: `${customDimensions.height}px`,
                }
              : {}
          }
        >
          <div
            className="absolute -top-2 -left-2 w-6 h-6 cursor-nw-resize opacity-60 hover:opacity-100 transition-opacity duration-200 z-10 group"
            onMouseDown={handleResizeStart}
          >
            <div className="w-full h-full bg-pink-600 rounded-full shadow-lg hover:bg-pink-700 transition-colors duration-200 flex items-center justify-center group-hover:scale-110 transform transition-transform">
              <div className="w-3 h-3 border-2 border-white rounded-full"></div>
            </div>
          </div>

          {/* Header */}
          <div className="bg-gradient-to-r from-pink-600 to-pink-700 text-white px-4 py-3 rounded-t-lg flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Scissors className="w-5 h-5 animate-pulse" />
              <h3 className="font-semibold text-sm"></h3>
              {(chatSize === "custom" || isResizing) && (
                <span className="text-xs opacity-75">
                  {customDimensions.width}×{customDimensions.height}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                onClick={toggleSize}
                variant="ghost"
                size="icon"
                className="w-6 h-6 text-white hover:bg-pink-700 transition-all duration-200 hover:scale-110"
                title={`Resize (${chatSize})`}
              >
                {chatSize === "small" ? (
                  <Maximize2 className="w-4 h-4 transition-transform duration-200 hover:rotate-12" />
                ) : chatSize === "large" ? (
                  <Minimize className="w-4 h-4 transition-transform duration-200 hover:rotate-12" />
                ) : (
                  <Maximize2 className="w-4 h-4 transition-transform duration-200 hover:rotate-12" />
                )}
              </Button>
              <Button
                onClick={() => setIsOpen(false)}
                variant="ghost"
                size="icon"
                className="w-6 h-6 text-white hover:bg-pink-700 transition-all duration-200 hover:scale-110"
              >
                <Minimize2 className="w-4 h-4 transition-transform duration-200 hover:rotate-12" />
              </Button>
              <Button
                onClick={() => setIsOpen(false)}
                variant="ghost"
                size="icon"
                className="w-6 h-6 text-white hover:bg-red-500 transition-all duration-200 hover:scale-110"
              >
                <X className="w-4 h-4 transition-transform duration-200 hover:rotate-90" />
              </Button>
            </div>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-3 space-y-3 bg-gradient-to-b from-gray-50 to-white">
            {messages.map((message, index) => (
              <div
                key={message.id}
                className={`flex ${
                  message.sender === "user" ? "justify-end" : "justify-start"
                } animate-in slide-in-from-bottom-2 fade-in duration-300`}
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div
                  className={`max-w-[85%] px-3 py-2 rounded-lg text-sm transition-all duration-300 hover:scale-[1.02] ${
                    message.sender === "user"
                      ? "bg-gradient-to-r from-pink-600 to-pink-700 text-white rounded-br-sm shadow-md hover:shadow-lg"
                      : "bg-white text-gray-900 border border-gray-200 rounded-bl-sm shadow-sm hover:shadow-md hover:border-pink-200"
                  }`}
                >
                  <p className="leading-relaxed">{message.content}</p>
                  <p className="text-xs opacity-60 mt-1">
                    {message.timestamp.toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>
            ))}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t border-gray-200 p-3 bg-white rounded-b-lg">
            <div className="flex gap-2">
              <Input
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder=""
                className="flex-1 text-sm h-8 transition-all duration-200 focus:scale-[1.02] focus:shadow-md"
                disabled={isLoading}
              />
              <Button
                onClick={sendMessage}
                disabled={!inputValue.trim() || isLoading}
                size="icon"
                className="bg-gradient-to-r from-pink-600 to-pink-700 hover:from-pink-700 hover:to-pink-800 h-8 w-8 transition-all duration-200 hover:scale-110 hover:shadow-lg disabled:hover:scale-100"
              >
                <Send className="w-3 h-3 transition-transform duration-200 hover:translate-x-0.5" />
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
