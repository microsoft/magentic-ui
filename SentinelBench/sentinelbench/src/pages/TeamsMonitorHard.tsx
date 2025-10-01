import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const PASSWORD_TeamsMonitorHard = "THATWASNTME";
export const TASK_ID_TeamsMonitorHard = "teams-monitor-hard";

interface Message {
  id: string;
  sender: string;
  content: string;
  timestamp: string;
  isUrgent: boolean;
  chatId: string;
  avatar: string;
}

interface Chat {
  id: string;
  name: string;
  participants: string[];
  lastMessage: string;
  timestamp: string;
  unreadCount: number;
  avatar: string;
  isOnline: boolean;
}

const TeamsMonitorHard = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const showHints = urlParams.get('hints') === 'true';
  
  // Validate duration parameter
  const taskDuration = (duration >= 1 && duration <= 86400) ? duration : DURATION.DEFAULT;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('duration') && taskDuration !== duration) {
      // Validation failed, emit error for toast
      const errors = [{
        parameter: 'duration',
        providedValue: urlParams.get('duration') || '',
        defaultUsed: DURATION.DEFAULT,
        reason: duration < 1 ? 'Value must be at least 1' : 
                duration > 86400 ? 'Value must be at most 86,400' :
                isNaN(duration) ? 'Value must be a valid number' : 'Invalid value'
      }];
      
      // Use the existing validation error system
      setTimeout(() => {
        URLParameterHandler.emitValidationError(errors);
      }, 100);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { duration: taskDuration, hasAnyParams: urlParams.has('duration') };

  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_TeamsMonitorHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_TeamsMonitorHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_TeamsMonitorHard);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        messages: [],
        chats: [],
        selectedChat: null,
        urgentMessageSent: false,
        pinnedMessages: [],
        penalties: 0,
        showPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_TeamsMonitorHard, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_TeamsMonitorHard, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        messages: (savedState.messages as Message[]) || [],
        chats: (savedState.chats as Chat[]) || [],
        selectedChat: (savedState.selectedChat as string | null) || null,
        urgentMessageSent: (savedState.urgentMessageSent as boolean) || false,
        pinnedMessages: (savedState.pinnedMessages as string[]) || [],
        penalties: (savedState.penalties as number) || 0,
        showPassword: (savedState.showPassword as boolean) || false,
        staticPassword: generateParameterPassword(TASK_ID_TeamsMonitorHard, savedDuration)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        messages: [],
        chats: [],
        selectedChat: null,
        urgentMessageSent: false,
        pinnedMessages: [],
        penalties: 0,
        showPassword: false,
        staticPassword: generateParameterPassword(TASK_ID_TeamsMonitorHard, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_TeamsMonitorHard, initialState);
      return initialState;
    }
  };

  const initialState = initializeState();
  
  // Clean URL after state is initialized
  useEffect(() => {
    if (params.hasAnyParams) {
      const cleanUrl = window.location.pathname;
      window.history.replaceState({}, '', cleanUrl);
    }
  }, []);
  
  const [startTime] = useState(initialState.startTime);
  const [teamsDuration] = useState(initialState.duration);
  const [messages, setMessages] = useState<Message[]>(initialState.messages);
  const [chats, setChats] = useState<Chat[]>(initialState.chats);
  const [selectedChat, setSelectedChat] = useState<string | null>(initialState.selectedChat);
  const [urgentMessageSent, setUrgentMessageSent] = useState(initialState.urgentMessageSent);
  const [pinnedMessages, setPinnedMessages] = useState<string[]>(initialState.pinnedMessages || []);
  const [penalties, setPenalties] = useState(initialState.penalties);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [typingIndicators, setTypingIndicators] = useState<Set<string>>(new Set());
  const [currentTime, setCurrentTime] = useState(Date.now());
  const timerRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_TeamsMonitorHard);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.urgentMessageSent && initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.urgentMessageSent, initialState.showPassword, recordSuccess]);

  useEffect(() => {
    timerRef.current = window.setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const getInitialChats = (): Chat[] => [
    {
      id: "general",
      name: "General",
      participants: ["Sarah Chen", "Mike Rodriguez", "Alex Kim", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "👥",
      isOnline: true
    },
    {
      id: "dev-team",
      name: "Development Team",
      participants: ["Emma Wilson", "James Liu", "Vaibhav Kumar", "Simon Miller", "Justin Ojah", "Raul Valle", "You"],
      lastMessage: "",
      timestamp: "", 
      unreadCount: 0,
      avatar: "💻",
      isOnline: true
    },
    {
      id: "project-alpha",
      name: "Project Alpha",
      participants: ["David Park", "Lisa Zhang", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "📋",
      isOnline: true
    },
    {
      id: "random",
      name: "Random",
      participants: ["Everyone"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "☕",
      isOnline: true
    },
    {
      id: "marketing",
      name: "Marketing Team",
      participants: ["Sarah Chen", "Rachel Torres", "Tom Wilson", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "📈",
      isOnline: true
    },
    {
      id: "announcements",
      name: "Company Announcements",
      participants: ["Everyone"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "📢",
      isOnline: true
    },
    {
      id: "social",
      name: "Water Cooler",
      participants: ["Mike Rodriguez", "Alex Kim", "Emma Wilson", "Rachel Torres", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "💬",
      isOnline: true
    },
    {
      id: "qa-team",
      name: "QA & Testing",
      participants: ["Lisa Zhang", "James Liu", "Kevin Lee", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "🧪",
      isOnline: true
    },
    {
      id: "lunch-group",
      name: "Lunch Crew",
      participants: ["David Park", "Sarah Chen", "Kevin Lee", "Tom Wilson", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "🍕",
      isOnline: true
    },
    {
      id: "tech-support",
      name: "IT Support",
      participants: ["Alex Kim", "Vaibhav Kumar", "Rachel Torres", "You"],
      lastMessage: "",
      timestamp: "",
      unreadCount: 0,
      avatar: "🔧",
      isOnline: true
    }
  ];

  const casualMessages = [
    { sender: "Sarah Chen", content: "Anyone want to grab ice cream after work?", chatId: "general" },
    { sender: "Mike Rodriguez", content: "That new restaurant downtown looks good", chatId: "random" },
    { sender: "Alex Kim", content: "Did everyone see the game last night?", chatId: "random" },
    { sender: "Emma Wilson", content: "The weather is perfect for a walk today", chatId: "general" },
    { sender: "James Liu", content: "My coffee machine broke, any recommendations?", chatId: "random" },
    { sender: "David Park", content: "Happy birthday to Lisa! 🎉", chatId: "project-alpha" },
    { sender: "Lisa Zhang", content: "Thanks everyone! Bringing cupcakes tomorrow", chatId: "project-alpha" },
    { sender: "Sarah Chen", content: "Anyone tried the new Thai place on 5th street?", chatId: "random" },
    { sender: "Mike Rodriguez", content: "My dog learned a new trick this weekend", chatId: "general" },
    { sender: "Alex Kim", content: "Planning a hiking trip next month, who's in?", chatId: "random" },
    { sender: "Emma Wilson", content: "Just finished reading a great book, highly recommend it", chatId: "general" },
    { sender: "James Liu", content: "The office plants need watering", chatId: "general" },
    { sender: "David Park", content: "Lunch meeting went well today", chatId: "project-alpha" },
    { sender: "Lisa Zhang", content: "Don't forget about the team photo session", chatId: "general" },
    { sender: "Sarah Chen", content: "My flight got delayed but made it home safely", chatId: "random" },
    { sender: "Mike Rodriguez", content: "The quarterly reports are due next week", chatId: "dev-team" },
    { sender: "Alex Kim", content: "Updated my LinkedIn profile finally", chatId: "random" },
    { sender: "Emma Wilson", content: "Code review looks good, thanks for the fixes", chatId: "dev-team" },
    { sender: "James Liu", content: "Meeting room A is available this afternoon", chatId: "project-alpha" },
    { sender: "David Park", content: "Client feedback was mostly positive", chatId: "project-alpha" },
    { sender: "Simon Miller", content: "Just pushed the latest feature branch", chatId: "dev-team" },
    { sender: "Justin Ojah", content: "Working on the new API documentation", chatId: "dev-team" },
    { sender: "Raul Valle", content: "Database optimization is running smoothly", chatId: "dev-team" }
  ];

  const ambiguousMessages = [
    { sender: "Emma Wilson", content: "The build is broken again, someone needs to fix it", chatId: "dev-team" },
    { sender: "James Liu", content: "My laptop screen broke this morning, need IT support", chatId: "general" },
    { sender: "Sarah Chen", content: "The printer broke down, can't print the reports", chatId: "general" },
    { sender: "Mike Rodriguez", content: "API endpoint is broken, getting 500 errors", chatId: "dev-team" },
    { sender: "Alex Kim", content: "Coffee machine broke, this is a real emergency!", chatId: "random" },
    { sender: "David Park", content: "The website broke on mobile, loading issues", chatId: "project-alpha" }
  ];

  const urgentMessage = {
    sender: "Vaibhav Kumar",
    content: "I accidentally wiped the user database while running cleanup scripts. All customer data is gone.",
    chatId: "dev-team",
    isUrgent: true
  };

  useEffect(() => {
    const currentState = {
      startTime,
      duration: teamsDuration,
      messages,
      chats,
      selectedChat,
      urgentMessageSent,
      pinnedMessages,
      penalties,
      showPassword,
      staticPassword
    };
    TaskStateManager.saveState(TASK_ID_TeamsMonitorHard, currentState);
  }, [startTime, teamsDuration, messages, chats, selectedChat, urgentMessageSent, pinnedMessages, penalties, showPassword, staticPassword]);

  useEffect(() => {
    if (chats.length === 0) {
      setChats(getInitialChats());
    }
    
    // Don't schedule any new messages if urgent message has already been sent
    if (urgentMessageSent) return;
    
    // Calculate optimal message spacing based on duration
    // Cap total messages at 50 to prevent storage issues
    const maxMessages = 50;
    const minInterval = 8000; // Minimum 8 seconds between messages
    const optimalInterval = Math.max(minInterval, (teamsDuration * 1000) / maxMessages);
    let messageCount = messages.length;
    
    const messageInterval = setInterval(() => {
      const elapsedSeconds = (Date.now() - startTime) / 1000;
      
      if (elapsedSeconds >= teamsDuration && !urgentMessageSent) {
        const newMessage: Message = {
          id: `urgent-${Date.now()}`,
          sender: urgentMessage.sender,
          content: urgentMessage.content,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isUrgent: true,
          chatId: urgentMessage.chatId,
          avatar: "👨‍💻"
        };
        
        setMessages(prev => [...prev, newMessage]);
        setUrgentMessageSent(true);
        
        setChats(prev => prev.map(chat => 
          chat.id === urgentMessage.chatId 
            ? { ...chat, lastMessage: urgentMessage.content, unreadCount: chat.unreadCount + 1, timestamp: newMessage.timestamp }
            : chat
        ));
        
        setTypingIndicators(prev => new Set([...prev, urgentMessage.sender]));
        setTimeout(() => {
          setTypingIndicators(prev => {
            const newSet = new Set(prev);
            newSet.delete(urgentMessage.sender);
            return newSet;
          });
        }, 2000);
        
      } else if (messageCount < maxMessages) {
        let selectedMessage;
        const shouldSendAmbiguous = Math.random() < 0.3 && elapsedSeconds > 30;
        
        if (shouldSendAmbiguous) {
          selectedMessage = ambiguousMessages[Math.floor(Math.random() * ambiguousMessages.length)];
        } else {
          selectedMessage = casualMessages[Math.floor(Math.random() * casualMessages.length)];
        }
        
        const newMessage: Message = {
          id: `msg-${Date.now()}`,
          sender: selectedMessage.sender,
          content: selectedMessage.content,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          isUrgent: false,
          chatId: selectedMessage.chatId,
          avatar: getAvatarForSender(selectedMessage.sender)
        };
        
        setMessages(prev => [...prev, newMessage]);
        messageCount++;
        
        setChats(prev => prev.map(chat => 
          chat.id === selectedMessage.chatId 
            ? { ...chat, lastMessage: selectedMessage.content, unreadCount: chat.unreadCount + 1, timestamp: newMessage.timestamp }
            : chat
        ));
        
        setTypingIndicators(prev => new Set([...prev, selectedMessage.sender]));
        setTimeout(() => {
          setTypingIndicators(prev => {
            const newSet = new Set(prev);
            newSet.delete(selectedMessage.sender);
            return newSet;
          });
        }, 1500);
      }
    }, optimalInterval);

    return () => clearInterval(messageInterval);
  }, [startTime, urgentMessageSent, teamsDuration, messages.length]);

  const getAvatarForSender = (sender: string) => {
    const avatars: { [key: string]: string } = {
      "Sarah Chen": "👩",
      "Mike Rodriguez": "👨",
      "Alex Kim": "👨‍💼",
      "Emma Wilson": "👩‍💻",
      "James Liu": "👨‍💻",
      "David Park": "👨‍🏫",
      "Lisa Zhang": "👩‍🔬",
      "Vaibhav Kumar": "👨‍💻",
      "Simon Miller": "👨‍🔧",
      "Justin Ojah": "👨‍💻",
      "Raul Valle": "👨‍🔬"
    };
    return avatars[sender] || "👤";
  };

  const handleChatSelect = (chatId: string) => {
    setSelectedChat(chatId);
    setChats(prev => prev.map(chat => 
      chat.id === chatId ? { ...chat, unreadCount: 0 } : chat
    ));
  };

  const handlePinMessage = (messageId: string) => {
    const message = messages.find(m => m.id === messageId);
    if (!message) return;

    if (message.isUrgent) {
      const finalPassword = generateParameterPassword(TASK_ID_TeamsMonitorHard, teamsDuration);
      setStaticPassword(finalPassword);
      setShowPassword(true);
      recordSuccess();
    } else {
      setPenalties((prev: number) => prev + 1);
    }
    
    if (!pinnedMessages.includes(messageId)) {
      setPinnedMessages(prev => [...prev, messageId]);
    }
  };

  const getPasswordWithPenalties = () => {
    return generateParameterPassword(TASK_ID_TeamsMonitorHard, teamsDuration);
  };

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the Teams monitoring.')) {
      TaskStateManager.clearState(TASK_ID_TeamsMonitorHard);
      window.location.reload();
    }
  };

  const elapsedTime = Math.floor((currentTime - startTime) / 1000);
  const isLocalhost = window.location.hostname === 'localhost';
  const [adminConsoleEnabled, setAdminConsoleEnabled] = useState(() => {
    return localStorage.getItem('adminConsoleEnabled') === 'true';
  });

  useEffect(() => {
    const handleAdminConsoleToggle = (e: CustomEvent) => {
      setAdminConsoleEnabled(e.detail.enabled);
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'adminConsoleEnabled') {
        setAdminConsoleEnabled(e.newValue === 'true');
      }
    };

    window.addEventListener('adminConsoleToggle', handleAdminConsoleToggle as EventListener);
    window.addEventListener('storage', handleStorageChange);
    
    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminConsoleToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  const filteredMessages = selectedChat 
    ? messages.filter(m => m.chatId === selectedChat)
    : [];

  return (
    <div className="h-screen bg-white flex flex-col">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Elapsed: {elapsedTime}s | 
              Duration: {teamsDuration}s |
              Messages: {messages.length} | 
              Urgent Sent: {urgentMessageSent ? '✅' : '❌'} | 
              Penalties: {penalties} |
              Persistent: {TaskStateManager.hasState(TASK_ID_TeamsMonitorHard) ? '✅' : '❌'}
            </div>
            <button 
              onClick={handleResetTask}
              className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-xs rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 shadow-sm"
            >
              Reset Task
            </button>
          </div>
        </div>
      )}
      
      <div className="flex flex-1">
      <div className="w-80 bg-gray-50 border-r border-gray-200 flex flex-col">
        <div className="p-4 border-b border-gray-200 bg-purple-600 text-white">
          <h1 className="text-lg font-semibold flex items-center">
            <span className="mr-2">💬</span>
            Microsoft Teams
          </h1>
        </div>

        <div className="p-3 border-b border-gray-200">
          <div className="relative">
            <input 
              type="text" 
              placeholder="Search chats..."
              className="w-full pl-8 pr-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
            <span className="absolute left-2 top-2 text-gray-400">🔍</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          {chats.map(chat => (
            <div
              key={chat.id}
              className={`p-3 cursor-pointer hover:bg-gray-100 border-b border-gray-100 ${
                selectedChat === chat.id ? 'bg-blue-50 border-l-4 border-l-blue-500' : ''
              }`}
              onClick={() => handleChatSelect(chat.id)}
            >
              <div className="flex items-start space-x-3">
                <div className="relative">
                  <span className="text-2xl">{chat.avatar}</span>
                  {chat.isOnline && (
                    <div className="absolute -bottom-1 -right-1 w-3 h-3 bg-green-500 rounded-full border-2 border-white"></div>
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">{chat.name}</h3>
                    <span className="text-xs text-gray-500">{chat.timestamp}</span>
                  </div>
                  <p className="text-xs text-gray-600 truncate mt-1">{chat.lastMessage}</p>
                  {typingIndicators.has(chat.name) && (
                    <p className="text-xs text-gray-500 italic mt-1">Someone is typing...</p>
                  )}
                </div>
                {chat.unreadCount > 0 && (
                  <div className="bg-red-500 text-white text-xs rounded-full px-2 py-1 min-w-[20px] h-5 flex items-center justify-center">
                    {chat.unreadCount}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="flex-1 flex flex-col">
        {selectedChat ? (
          <>
            <div className="p-4 border-b border-gray-200 bg-white">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">{chats.find(c => c.id === selectedChat)?.avatar}</span>
                  <h2 className="text-lg font-semibold">{chats.find(c => c.id === selectedChat)?.name}</h2>
                </div>
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <span>📞</span>
                  <span>📹</span>
                  <span>⚙️</span>
                </div>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {filteredMessages.map(message => (
                <div key={message.id} className="flex items-start space-x-3 group">
                  <span className="text-2xl flex-shrink-0">{message.avatar}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-sm font-semibold text-gray-900">{message.sender}</span>
                      <span className="text-xs text-gray-500">{message.timestamp}</span>
                    </div>
                    <div className="bg-gray-100 rounded-lg p-3 max-w-lg">
                      <p className="text-sm text-gray-800">{message.content}</p>
                    </div>
                    
                    <div className="mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handlePinMessage(message.id)}
                        disabled={pinnedMessages.includes(message.id)}
                        className={`text-xs px-2 py-1 rounded ${
                          pinnedMessages.includes(message.id)
                            ? 'bg-yellow-200 text-yellow-800 cursor-not-allowed'
                            : 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                        }`}
                      >
                        {pinnedMessages.includes(message.id) ? '📌 Pinned' : '📌 Pin Message'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              
              {Array.from(typingIndicators).map(sender => (
                <div key={sender} className="flex items-start space-x-3">
                  <span className="text-2xl">{getAvatarForSender(sender)}</span>
                  <div className="bg-gray-100 rounded-lg p-3">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div className="p-4 border-t border-gray-200 bg-white">
              <div className="flex items-center space-x-2">
                <input
                  type="text"
                  placeholder="Type a message..."
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                />
                <button className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700">
                  Send
                </button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center bg-gray-50">
            <div className="text-center">
              <span className="text-6xl mb-4 block">💬</span>
              <h2 className="text-xl font-semibold text-gray-700 mb-2">Select a chat to start messaging</h2>
              <p className="text-gray-500">Choose from your conversations on the left</p>
            </div>
          </div>
        )}
      </div>

      {showPassword && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white p-8 rounded-lg shadow-xl max-w-md">
            <h2 className="text-2xl font-bold text-green-800 mb-4 text-center">
              📌 Urgent Message Pinned!
            </h2>
            <p className="text-gray-700 text-center mb-4">
              You successfully pinned the urgent message that needed attention.
            </p>
            {penalties > 0 && (
              <p className="text-amber-600 text-center mb-4 text-sm">
                Note: {penalties} incorrect pin{penalties !== 1 ? 's' : ''} applied
              </p>
            )}
            <div className="bg-green-100 p-4 rounded-lg text-center">
              <p className="text-green-800 font-medium mb-2">Access Code:</p>
              <code className="font-mono font-bold text-lg">{staticPassword || getPasswordWithPenalties()}</code>
            </div>
          </div>
        </div>
      )}

      {/* Technical Details */}
      {showHints && (
        <div className="bg-gray-900 text-green-400 rounded-lg p-6 mt-6 border-2 border-green-500 font-mono">
          <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
          <div className="text-sm space-y-2">
            <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#teams-monitor-status</code></p>
            <p><strong className="text-yellow-400">✅ Completion State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="completed"</code></p>
            <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#teams-monitor-code</code></p>
            <p><strong className="text-yellow-400">⏱️ Timer:</strong> {Math.floor(teamsDuration / 60)}:{(teamsDuration % 60).toString().padStart(2, '0')} minutes countdown</p>
            <p><strong className="text-yellow-400">📡 Current State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="{showPassword ? 'completed' : 'monitoring'}"</code></p>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};

export default TeamsMonitorHard;