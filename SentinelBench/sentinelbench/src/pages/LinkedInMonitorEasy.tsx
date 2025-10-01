import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_LinkedInMonitorEasy = "linkedin-monitor-easy";

interface Post {
  id: string;
  author: string;
  title: string;
  company: string;
  content: string;
  timestamp: string;
  likes: number;
  comments: number;
  shares: number;
  avatar: string;
  isMagenticPost: boolean;
  hashtags?: string[];
}

// Generate consistent engagement values based on post ID
const getEngagementValues = (postId: string) => {
  // Create multiple hash values for better distribution
  let hash1 = 5381;
  let hash2 = 0;
  let hash3 = 1;
  
  for (let i = 0; i < postId.length; i++) {
    const char = postId.charCodeAt(i);
    hash1 = ((hash1 << 5) + hash1) + char; // djb2 hash
    hash2 = char + (hash2 << 6) + (hash2 << 16) - hash2; // sdbm hash
    hash3 = hash3 * 31 + char; // simple multiplicative hash
  }
  
  // Use different hashes for each metric to ensure variety
  const likes = (Math.abs(hash1) % 190) + 10; // 10-199 range
  const comments = (Math.abs(hash2) % 48) + 2; // 2-49 range  
  const shares = (Math.abs(hash3) % 19) + 1; // 1-19 range
  
  return { likes, comments, shares };
};

const LinkedInMonitorEasy = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const validDuration = isNaN(duration) || duration < 1 || duration > 86400 ? 30 : duration;
  const showHints = urlParams.get('hints') === 'true';
  
  // Create params object for shouldResetState check
  const params = { duration: validDuration, hasAnyParams: urlParams.has('duration') };

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_LinkedInMonitorEasy);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_LinkedInMonitorEasy, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_LinkedInMonitorEasy);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: validDuration,
        posts: [],
        targetPostSent: false,
        penalties: 0,
        showPassword: false,
        replyAttempts: [],
        staticPassword: generateParameterPassword(TASK_ID_LinkedInMonitorEasy, validDuration),
        allPosts: []
      };
      
      TaskStateManager.saveState(TASK_ID_LinkedInMonitorEasy, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state
      const savedDuration = (savedState.duration as number) || validDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        posts: (savedState.posts as Post[]) || [],
        targetPostSent: (savedState.targetPostSent as boolean) || (savedState.magenticPostSent as boolean) || false,
        penalties: (savedState.penalties as number) || 0,
        showPassword: (savedState.showPassword as boolean) || false,
        replyAttempts: (savedState.replyAttempts as string[]) || [],
        staticPassword: generateParameterPassword(TASK_ID_LinkedInMonitorEasy, savedDuration),
        allPosts: (savedState.allPosts as Post[]) || []
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: validDuration,
        posts: [],
        targetPostSent: false,
        penalties: 0,
        showPassword: false,
        replyAttempts: [],
        staticPassword: generateParameterPassword(TASK_ID_LinkedInMonitorEasy, validDuration),
        allPosts: []
      };
      
      TaskStateManager.saveState(TASK_ID_LinkedInMonitorEasy, initialState);
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

  // Emit validation errors for invalid duration parameters
  useEffect(() => {
    if (urlParams.has('duration')) {
      const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
      if (isNaN(duration) || duration < 1 || duration > 86400) {
        const errors = [{
          parameter: 'duration',
          providedValue: urlParams.get('duration') || '',
          defaultUsed: 30,
          reason: duration < 1 ? 'Duration must be at least 1 second' : 
                   duration > 86400 ? 'Duration must be at most 86400 seconds (24 hours)' : 
                   isNaN(duration) ? 'Value must be a valid number' : 'Invalid duration value'
        }];
        
        setTimeout(() => {
          URLParameterHandler.emitValidationError(errors);
        }, 100);
      }
    }
  }, []);
  const [startTime] = useState(initialState.startTime);
  const [linkedinDuration] = useState(initialState.duration);
  const [posts, setPosts] = useState<Post[]>(initialState.posts);
  const [targetPostSent, setTargetPostSent] = useState(initialState.targetPostSent);
  const [penalties, setPenalties] = useState(initialState.penalties);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [replyAttempts, setReplyAttempts] = useState<string[]>(initialState.replyAttempts);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [replyAttempt, setReplyAttempt] = useState<string | null>(null);
  const feedRef = useRef<HTMLDivElement>(null);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [searchQuery, setSearchQuery] = useState("");
  const [allPosts, setAllPosts] = useState<Post[]>(initialState.allPosts);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_LinkedInMonitorEasy);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword && initialState.targetPostSent) {
      recordSuccess();
    }
  }, [initialState.showPassword, initialState.targetPostSent, recordSuccess]);

  // Update current time every second for live elapsed time display
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const regularPosts = [
    {
      author: "Jennifer Smith",
      title: "Senior Software Engineer",
      company: "TechFlow Solutions",
      content: "Just got promoted to Lead Developer! 🎉 Grateful for the amazing team that made this journey possible. Excited for the new challenges ahead!",
      avatar: "👩‍💻",
      hashtags: ["#promotion", "#grateful", "#leadership"]
    },
    {
      author: "David Rodriguez",
      title: "Product Manager",
      company: "InnovateCorp",
      content: "5 key trends I'm seeing in fintech this year: 1) Embedded banking 2) AI-powered fraud detection 3) Real-time payments 4) Digital identity 5) Sustainable finance. What trends are you watching?",
      avatar: "👨‍💼",
      hashtags: ["#fintech", "#innovation", "#trends"]
    },
    {
      author: "Sarah Kim",
      title: "UX Designer",
      company: "DesignHub",
      content: "Amazing networking event at the Design Conference last night! Met so many talented professionals and learned about cutting-edge design methodologies. The future of user experience is bright! ✨",
      avatar: "👩‍🎨",
      hashtags: ["#networking", "#design", "#UX"]
    },
    {
      author: "Michael Chen",
      title: "Data Scientist",
      company: "Analytics Pro",
      content: "We're hiring! Looking for a passionate Data Analyst to join our growing team. If you love working with big data and want to make an impact, send me a message. Remote-friendly position! 📊",
      avatar: "👨‍🔬",
      hashtags: ["#hiring", "#analytics", "#remote"]
    },
    {
      author: "Lisa Wang",
      title: "Marketing Director",
      company: "BrandCo",
      content: "Just wrapped up our Q1 campaign and the results exceeded expectations by 150%! Proud of the creative team for their outstanding work. Sometimes the best strategies come from thinking outside the box.",
      avatar: "👩‍💼",
      hashtags: ["#marketing", "#teamwork", "#results"]
    },
    {
      author: "Alex Thompson",
      title: "DevOps Engineer",
      company: "CloudTech",
      content: "Spent the weekend learning Kubernetes and I'm blown away by its capabilities. The orchestration possibilities are endless. Any recommendations for advanced tutorials?",
      avatar: "👨‍💻",
      hashtags: ["#kubernetes", "#devops", "#learning"]
    },
    {
      author: "Emily Davis",
      title: "HR Business Partner",
      company: "People First Inc",
      content: "Completed my certification in diversity and inclusion training. It's incredible how small changes in our hiring process can create big impacts on company culture. Progress starts with awareness! 🌟",
      avatar: "👩‍💼",
      hashtags: ["#diversity", "#inclusion", "#HR"]
    },
    {
      author: "Robert Johnson",
      title: "Sales Manager",
      company: "SalesForce Elite",
      content: "Closed the biggest deal of my career today! 🚀 Persistence and understanding client needs really pays off. Celebrating with the team tonight - they deserve all the credit!",
      avatar: "👨‍💼",
      hashtags: ["#sales", "#teamwork", "#milestone"]
    },
    {
      author: "Anna Martinez",
      title: "Content Creator",
      company: "Creative Studios",
      content: "Just published my article on the future of content marketing. The landscape is changing rapidly with AI tools, but authentic storytelling remains king. Link in comments! 📝",
      avatar: "👩‍🎨",
      hashtags: ["#contentmarketing", "#storytelling", "#AI"]
    },
    {
      author: "James Wilson",
      title: "Cybersecurity Specialist",
      company: "SecureNet",
      content: "Reminder: Update your passwords regularly and enable 2FA everywhere! Saw too many preventable breaches this month. Your digital security is worth the extra 2 minutes. Stay safe out there! 🔒",
      avatar: "👨‍🔒",
      hashtags: ["#cybersecurity", "#safety", "#2FA"]
    }
  ];

  const targetPost = {
    author: "Dr. Sarah Chen",
    title: "Director of Education",
    company: "Data Science Organization",
    content: "Exciting news! 📊 The Data Science Organization is hosting new workshops in the realm of data science this quarter. We're covering machine learning fundamentals, statistical analysis, and advanced visualization techniques. Join us to expand your data science skills and connect with fellow practitioners in our community! Registration opens Monday.",
    avatar: "👩‍🔬",
    hashtags: ["#datascience", "#workshops", "#learning"],
    isMagenticPost: true
  };

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: linkedinDuration,
      posts,
      targetPostSent,
      penalties,
      showPassword,
      replyAttempts,
      staticPassword,
      allPosts
    };
    
    TaskStateManager.saveState(TASK_ID_LinkedInMonitorEasy, currentState);
  }, [startTime, linkedinDuration, posts, targetPostSent, penalties, showPassword, replyAttempts, staticPassword, allPosts]);

  // Duration-based post scheduling (Easy mode - stops after target)  
  useEffect(() => {
    // Don't schedule any new posts if target has already been sent
    if (targetPostSent) return;
    
    const postInterval = Math.max(1, Math.floor(linkedinDuration / 5)); // 5 total posts (4 regular + 1 target)
    const timeouts: NodeJS.Timeout[] = [];
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    
    // Clear any existing posts and regenerate based on timing
    const postsToGenerate = [];
    
    // Generate all posts that should have already appeared (only those that should appear before or at target time)
    for (let i = 0; i < 4; i++) {
      const postShouldAppearAt = (i + 1) * postInterval; // in seconds
      
      // Only include posts that should appear before the target post
      if (elapsedSeconds >= postShouldAppearAt && postShouldAppearAt < linkedinDuration) {
        const postIndex = i % regularPosts.length;
        const selectedPost = regularPosts[postIndex];
        const newPost: Post = {
          id: `post-scheduled-${i}`,
          ...selectedPost,
          timestamp: new Date(startTime + postShouldAppearAt * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          ...getEngagementValues(`post-scheduled-${i}-${selectedPost.author}-${postIndex}`),
          isMagenticPost: false
        };
        postsToGenerate.push(newPost);
      }
    }
    
    // Add target post if it should have appeared
    if (elapsedSeconds >= linkedinDuration) {
      const targetPostInstance: Post = {
        id: 'magentic-target',
        ...targetPost,
        timestamp: new Date(startTime + linkedinDuration * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        likes: 45,
        comments: 12,
        shares: 8,
        isMagenticPost: true
      };
      postsToGenerate.push(targetPostInstance);
      setTargetPostSent(true);
    }
    
    // Set all posts that should exist right now
    if (postsToGenerate.length > 0) {
      setAllPosts(postsToGenerate.reverse()); // Reverse to show newest first
      
      // Save state immediately
      TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorEasy, {
        startTime,
        duration: linkedinDuration,
        posts: postsToGenerate,
        targetPostSent: elapsedSeconds >= linkedinDuration,
        penalties,
        showPassword: elapsedSeconds >= linkedinDuration ? showPassword : false,
        replyAttempts,
        staticPassword,
        allPosts: postsToGenerate
      });
    }
    
    // Schedule future posts (only those that should appear before target)
    for (let i = 0; i < 4; i++) {
      const postShouldAppearAt = (i + 1) * postInterval;
      
      // Only schedule posts that haven't appeared yet and should appear before the target
      if (elapsedSeconds < postShouldAppearAt && postShouldAppearAt < linkedinDuration) {
        const delay = (postShouldAppearAt - elapsedSeconds) * 1000;
        const timeout = setTimeout(() => {
          const postIndex = i % regularPosts.length;
          const selectedPost = regularPosts[postIndex];
          const newPost: Post = {
            id: `post-scheduled-${i}`,
            ...selectedPost,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            ...getEngagementValues(`post-scheduled-${i}-${selectedPost.author}-${postIndex}`),
            isMagenticPost: false
          };
          
          setAllPosts(prev => {
            const updatedPosts = [newPost, ...prev];
            
            // Save state immediately when new post appears
            TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorEasy, {
              startTime,
              duration: linkedinDuration,
              posts: updatedPosts,
              targetPostSent,
              penalties,
              showPassword,
              replyAttempts,
              staticPassword,
              allPosts: updatedPosts
            });
            
            return updatedPosts;
          });
          
          // Auto scroll to top to show new post
          if (feedRef.current) {
            feedRef.current.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }, delay);
        
        timeouts.push(timeout);
      }
    }
    
    // Schedule target post if not appeared yet
    if (elapsedSeconds < linkedinDuration) {
      const delay = (linkedinDuration - elapsedSeconds) * 1000;
      const targetTimeout = setTimeout(() => {
        if (!targetPostSent) {
          const newPost: Post = {
            id: 'magentic-target',
            ...targetPost,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            likes: 45,
            comments: 12,
            shares: 8,
            isMagenticPost: true
          };
          
          setAllPosts(prev => [newPost, ...prev]);
          setTargetPostSent(true);
          
          // Save state immediately when target post appears
          TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorEasy, {
            startTime,
            duration: linkedinDuration,
            posts: [newPost, ...allPosts],
            targetPostSent: true,
            penalties,
            showPassword,
            replyAttempts,
            staticPassword,
            allPosts: [newPost, ...allPosts]
          });
          
          // Auto scroll to top to show new post
          if (feedRef.current) {
            feedRef.current.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }
      }, delay);
      
      timeouts.push(targetTimeout);
    }
    
    // Cleanup function
    return () => {
      timeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [startTime, linkedinDuration]); // Only depend on startTime and linkedinDuration

  // Filter posts based on search query
  const filteredPosts = searchQuery.trim() 
    ? allPosts.filter(post => 
        post.content.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : allPosts;

  // Update displayed posts when search changes
  useEffect(() => {
    setPosts(filteredPosts);
  }, [filteredPosts]);

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  const handleReply = (postId: string) => {
    const post = posts.find(p => p.id === postId);
    if (!post) return;

    // Track all reply attempts
    setReplyAttempts(prev => [...prev, postId]);
    
    // Save state immediately when user clicks on post
    TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorEasy, {
      startTime,
      duration: linkedinDuration,
      posts,
      targetPostSent,
      penalties: post.isMagenticPost ? penalties : penalties + 1,
      showPassword: post.isMagenticPost ? true : showPassword,
      replyAttempts: [...replyAttempts, postId],
      staticPassword: post.isMagenticPost ? generateParameterPassword(TASK_ID_LinkedInMonitorEasy, linkedinDuration) : staticPassword,
      allPosts
    });

    if (post.isMagenticPost) {
      const finalPassword = generateParameterPassword(TASK_ID_LinkedInMonitorEasy, linkedinDuration);
      setStaticPassword(finalPassword);
      setShowPassword(true);
      recordSuccess();
    } else {
      setPenalties((prev: number) => prev + 1);
      setReplyAttempt(postId);
      setTimeout(() => setReplyAttempt(null), 3000);
    }
  };

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the LinkedIn monitoring from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_LinkedInMonitorEasy);
      // Reload with default duration instead of saved duration
      window.location.href = `${window.location.pathname}?duration=${DURATION.DEFAULT}`;
    }
  };

  const elapsedTime = Math.floor((currentTime - startTime) / 1000);
  const isLocalhost = window.location.hostname === 'localhost';
  const [adminConsoleEnabled, setAdminConsoleEnabled] = useState(() => {
    const stored = localStorage.getItem('adminConsoleEnabled');
    return stored === 'true';
  });

  // Listen for admin console toggle events and sync with localStorage
  useEffect(() => {
    const handleAdminToggle = (e: CustomEvent) => {
      setAdminConsoleEnabled(e.detail.enabled);
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'adminConsoleEnabled') {
        setAdminConsoleEnabled(e.newValue === 'true');
      }
    };

    // Check for updates to localStorage value periodically
    const syncWithStorage = () => {
      const currentValue = localStorage.getItem('adminConsoleEnabled') === 'true';
      setAdminConsoleEnabled(currentValue);
    };

    window.addEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
    window.addEventListener('storage', handleStorageChange);
    
    // Sync every 2 seconds in case localStorage changes from another tab
    const interval = setInterval(syncWithStorage, 2000);

    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  const getPasswordWithPenalties = () => {
    return generateParameterPassword(TASK_ID_LinkedInMonitorEasy, linkedinDuration);
  };

  const formatHashtags = (hashtags?: string[]) => {
    return hashtags?.map((tag, index) => (
      <span key={index} className="text-blue-600 hover:underline cursor-pointer mr-1">
        {tag}
      </span>
    ));
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="max-w-6xl mx-auto px-4">
          <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
            <div className="flex items-center justify-between text-sm">
              <div className="text-yellow-800 font-medium">
                <strong>Dev Tools:</strong> Duration: {linkedinDuration}s | Elapsed: {elapsedTime}s | 
                Posts: {posts.length} | 
                Target Sent: {targetPostSent ? '✅' : '❌'} | 
                Shares: {replyAttempts.length} | 
                Penalties: {penalties} |
                Persistent: {TaskStateManager.hasState(TASK_ID_LinkedInMonitorEasy) ? '✅' : '❌'}
              </div>
              <button 
                onClick={handleResetTask}
                className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-xs rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 shadow-sm"
              >
                Reset Task
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* LinkedIn Header */}
      <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <div className="text-2xl font-bold text-blue-600">in</div>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search"
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="w-64 pl-8 pr-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <span className="absolute left-2 top-2 text-gray-400">🔍</span>
              </div>
            </div>
            <nav className="flex items-center space-x-6 text-sm text-gray-600">
              <div className="flex flex-col items-center cursor-pointer hover:text-blue-600">
                <span>🏠</span>
                <span>Home</span>
              </div>
              <div className="flex flex-col items-center cursor-pointer hover:text-blue-600">
                <span>👥</span>
                <span>Network</span>
              </div>
              <div className="flex flex-col items-center cursor-pointer hover:text-blue-600">
                <span>💼</span>
                <span>Jobs</span>
              </div>
              <div className="flex flex-col items-center cursor-pointer hover:text-blue-600">
                <span>💬</span>
                <span>Messaging</span>
              </div>
              <div className="flex flex-col items-center cursor-pointer hover:text-blue-600">
                <span>🔔</span>
                <span>Notifications</span>
              </div>
              <div className="flex flex-col items-center cursor-pointer hover:text-blue-600">
                <span>👤</span>
                <span>Me</span>
              </div>
            </nav>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto py-6 px-4 flex space-x-6">
        {/* Minimal Left Sidebar for Easy Mode */}
        <div className="w-64 space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-2xl">👤</span>
              </div>
              <h3 className="font-semibold">You</h3>
              <p className="text-sm text-gray-500">Software Engineer</p>
            </div>
          </div>
        </div>

        {/* Main Feed */}
        <div className="flex-1 space-y-4" ref={feedRef} style={{ maxHeight: '80vh', overflowY: 'auto' }}>
          {/* Post Composer */}
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center space-x-3">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                <span className="text-xl">👤</span>
              </div>
              <input
                type="text"
                placeholder="Start a post..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-200">
              <div className="flex space-x-4 text-sm text-gray-600">
                <span className="cursor-pointer hover:bg-gray-100 px-3 py-1 rounded">📷 Photo</span>
                <span className="cursor-pointer hover:bg-gray-100 px-3 py-1 rounded">📹 Video</span>
                <span className="cursor-pointer hover:bg-gray-100 px-3 py-1 rounded">📄 Document</span>
              </div>
            </div>
          </div>

          {/* Posts */}
          {posts.map((post) => (
            <div key={post.id} className="bg-white rounded-lg border border-gray-200">
              {/* Post Header */}
              <div className="p-4 flex items-start space-x-3">
                <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <span className="text-xl">{post.avatar}</span>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold hover:text-blue-600 cursor-pointer">{post.author}</h3>
                  <p className="text-sm text-gray-600">{post.title} at {post.company}</p>
                  <p className="text-xs text-gray-500">{post.timestamp}</p>
                </div>
                <button className="text-gray-400 hover:text-gray-600">⋯</button>
              </div>

              {/* Post Content */}
              <div className="px-4 pb-4">
                <div className="whitespace-pre-line text-sm text-gray-800 mb-3">
                  {post.content}
                </div>
                {post.hashtags && (
                  <div className="mb-3">
                    {formatHashtags(post.hashtags)}
                  </div>
                )}
              </div>

              {/* Post Stats */}
              <div className="px-4 py-2 border-t border-gray-200 flex items-center justify-between text-sm text-gray-500">
                <div className="flex items-center space-x-4">
                  <span>❤️ {post.likes}</span>
                  <span>{post.comments} comments</span>
                  <span>{post.shares} shares</span>
                </div>
              </div>

              {/* Post Actions */}
              <div className="px-4 py-2 border-t border-gray-200 flex items-center justify-between">
                <button className="flex items-center space-x-2 text-sm text-gray-600 hover:bg-gray-50 px-3 py-2 rounded">
                  <span>👍</span>
                  <span>Like</span>
                </button>
                <button 
                  onClick={() => {}}
                  className="flex items-center space-x-2 text-sm text-gray-600 hover:bg-gray-50 px-3 py-2 rounded"
                >
                  <span>💬</span>
                  <span>Comment</span>
                </button>
                <button 
                  onClick={() => handleReply(post.id)}
                  className="flex items-center space-x-2 text-sm text-gray-600 hover:bg-gray-50 px-3 py-2 rounded"
                >
                  <span>↗️</span>
                  <span>Share</span>
                </button>
              </div>

              {/* Reply Attempt Message */}
              {replyAttempt === post.id && (
                <div className="px-4 py-2 bg-red-50 border-t border-red-200">
                  <p className="text-sm text-red-600">You are unable to share at this time, try again later</p>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Minimal Right Sidebar for Easy Mode */}
        <div className="w-80 space-y-4">
          {/* Intentionally minimal - no distractions */}
        </div>
      </div>

      {/* Success Modal - Non-blocking */}
      {showPassword && (
        <div className="fixed top-4 right-4 z-50 max-w-sm">
          <div className="bg-white p-6 rounded-lg shadow-xl border-2 border-green-500">
            <div className="flex items-center justify-between mb-4">
              <div 
                id="linkedin-monitor-status"
                data-state="completed"
                className="text-center p-3 rounded-lg font-bold text-lg bg-green-600 text-white flex-1"
              >
                🎯 Data Science Post Found!
              </div>
              <button 
                onClick={() => setShowPassword(false)}
                className="ml-2 text-gray-500 hover:text-gray-700 text-xl font-bold"
              >
                ×
              </button>
            </div>
            <p className="text-gray-700 text-center mb-3 text-sm">
              You successfully identified and shared the Data Science Organization post!
            </p>
            <div className="bg-green-100 p-3 rounded-lg text-center">
              <p className="text-green-800 font-medium mb-1 text-sm">Access Code:</p>
              <span id="linkedin-monitor-code" className="font-mono font-bold text-base">{staticPassword || getPasswordWithPenalties()}</span>
            </div>
          </div>
        </div>
      )}
      
      {/* Technical Details */}
      {showHints && (
        <div className="bg-gray-900 text-green-400 rounded-lg p-6 mt-6 border-2 border-green-500 font-mono">
          <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
          <div className="text-sm space-y-2">
            <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#linkedin-monitor-status</code></p>
            <p><strong className="text-yellow-400">✅ Completion State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="completed"</code></p>
            <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#linkedin-monitor-code</code></p>
            <p><strong className="text-yellow-400">⏱️ Timer:</strong> {Math.floor(linkedinDuration / 60)}:{(linkedinDuration % 60).toString().padStart(2, '0')} minutes countdown</p>
            <p><strong className="text-yellow-400">📡 Current State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="{showPassword ? 'completed' : 'monitoring'}"</code></p>
          </div>
        </div>
      )}
    </div>
  );
};

export default LinkedInMonitorEasy;