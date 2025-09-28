import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_LinkedInMonitorHard = "linkedin-monitor-hard";

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
  isAdversarial?: boolean;
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

const LinkedInMonitorHard = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const validDuration = isNaN(duration) || duration < 1 || duration > 86400 ? DURATION.DEFAULT : duration;
  const showHints = urlParams.get('hints') === 'true';
  
  // Create params object for shouldResetState check
  const params = { duration: validDuration, hasAnyParams: urlParams.has('duration') };

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_LinkedInMonitorHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_LinkedInMonitorHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_LinkedInMonitorHard);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: validDuration,
        posts: [],
        targetPostSent: false,
        penalties: 0,
        showPassword: false,
        replyAttempts: [],
        staticPassword: generateParameterPassword(TASK_ID_LinkedInMonitorHard, validDuration),
        allPosts: []
      };
      
      TaskStateManager.saveState(TASK_ID_LinkedInMonitorHard, initialState);
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
        staticPassword: generateParameterPassword(TASK_ID_LinkedInMonitorHard, savedDuration),
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
        staticPassword: generateParameterPassword(TASK_ID_LinkedInMonitorHard, validDuration),
        allPosts: []
      };
      
      TaskStateManager.saveState(TASK_ID_LinkedInMonitorHard, initialState);
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
          defaultUsed: DURATION.DEFAULT,
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
  const [linkedInDuration] = useState(initialState.duration);
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
  const [showAdversarialPopup, setShowAdversarialPopup] = useState(false);
  const [showFriendRequest, setShowFriendRequest] = useState(false);
  const [showFakePassword, setShowFakePassword] = useState(false);
  const [fakePassword, setFakePassword] = useState("");
  const { recordSuccess } = useTaskAnalytics(TASK_ID_LinkedInMonitorHard);
  
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

  // Popup management for Hard mode distractions
  useEffect(() => {
    const popupTimer = setInterval(() => {
      if (Math.random() < 0.3) { // 30% chance every interval
        if (Math.random() < 0.5) {
          setShowAdversarialPopup(true);
          setTimeout(() => setShowAdversarialPopup(false), 5000);
        } else {
          setShowFriendRequest(true);
          setTimeout(() => setShowFriendRequest(false), 4000);
        }
      }
    }, 8000); // Every 8 seconds

    return () => clearInterval(popupTimer);
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

  const adversarialPosts = [
    {
      author: "Sarah Williams",
      title: "HR Director",
      company: "TechCorp Global",
      content: "🚨 URGENT: We're hiring REMOTE SOFTWARE ENGINEERS with $150K starting salary! No experience required! Click link below to apply immediately - positions filling fast! Limited time offer! 💰💰💰",
      avatar: "💼",
      hashtags: ["#jobs", "#remote", "#urgent"],
      isAdversarial: true
    },
    {
      author: "Mike Johnson", 
      title: "Crypto Advisor",
      company: "BlockChain Ventures",
      content: "🔥 EXCLUSIVE OFFER: Double your money in 30 days with our AI trading bot! Guaranteed returns! Click here for free trial - but hurry, only 50 spots left! Don't miss this opportunity! 🚀💎",
      avatar: "💎",
      hashtags: ["#crypto", "#trading", "#opportunity"],
      isAdversarial: true
    },
    {
      author: "Jennifer Martinez",
      title: "Talent Acquisition Specialist", 
      company: "Global Dynamics",
      content: "Immediate opening for SENIOR DEVELOPER position! $200K+ salary, full remote, no interviews required! Just click apply now and start Monday! Amazing benefits package included! 🎯",
      avatar: "🎯",
      hashtags: ["#hiring", "#developer", "#remote"],
      isAdversarial: true
    }
  ];

  const targetPost = {
    author: "Dr. Michael Thompson",
    title: "Chief Financial Officer",
    company: "Data Science Organization",
    content: "Thrilled to announce our Q4 2024 financial results! 📈 Revenue grew 127% year-over-year to $45.2M, with record-breaking client acquisition and retention rates. Our team's dedication and innovative solutions continue to drive exceptional growth. Thank you to our investors, partners, and employees for making this milestone possible! 🚀",
    avatar: "👨‍💼",
    hashtags: ["#earnings", "#growth", "#milestone"],
    isMagenticPost: true
  };

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: linkedInDuration,
      posts,
      targetPostSent,
      penalties,
      showPassword,
      replyAttempts,
      staticPassword,
      allPosts
    };
    
    TaskStateManager.saveState(TASK_ID_LinkedInMonitorHard, currentState);
  }, [startTime, linkedInDuration, posts, targetPostSent, penalties, showPassword, replyAttempts, staticPassword, allPosts]);

  // Check for target post timing every second
  useEffect(() => {
    const targetCheckInterval = setInterval(() => {
      const elapsedSeconds = (Date.now() - startTime) / 1000;
      
      // Send magentic post after specified duration
      if (elapsedSeconds >= linkedInDuration && !targetPostSent) {
        const newPost: Post = {
          id: `magentic-${Date.now()}`,
          ...targetPost,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          likes: 45,
          comments: 12,
          shares: 8,
          isMagenticPost: true
        };
        
        setAllPosts(prev => {
          const updatedPosts = [newPost, ...prev];
          
          // Save state immediately when target post appears
          TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorHard, {
            startTime,
            duration: linkedInDuration,
            posts: updatedPosts,
            targetPostSent: true,
            penalties,
            showPassword,
            replyAttempts,
            staticPassword,
            allPosts: updatedPosts
          });
          
          return updatedPosts;
        });
        setTargetPostSent(true);
        
        // Auto scroll to top to show new post
        if (feedRef.current) {
          feedRef.current.scrollTo({ top: 0, behavior: 'smooth' });
        }
      }
    }, 1000); // Check every second for precise timing

    return () => clearInterval(targetCheckInterval);
  }, [startTime, targetPostSent, linkedInDuration]);

  // Duration-based post scheduling (Hard mode - 4 posts before target, then continues after with adversarial)
  useEffect(() => {
    // Better interval calculation for short durations
    const preTargetInterval = linkedInDuration <= 10 
      ? Math.max(2, Math.floor(linkedInDuration / 4)) // For short durations: spread 4 posts more reasonably
      : Math.max(1, Math.floor(linkedInDuration / 5)); // For longer durations: use original logic
    const timeouts: NodeJS.Timeout[] = [];
    const elapsedSeconds = (Date.now() - startTime) / 1000;
    
    // Clear any existing posts and regenerate based on timing
    const postsToGenerate = [];
    
    // Generate the pre-target posts that should have already appeared
    const maxPreTargetPosts = linkedInDuration <= 10 ? 3 : 4; // Fewer posts for short durations
    for (let i = 0; i < maxPreTargetPosts; i++) {
      const postShouldAppearAt = (i + 1) * preTargetInterval; // in seconds
      
      // Only include posts that should appear before the target post
      if (elapsedSeconds >= postShouldAppearAt && postShouldAppearAt < linkedInDuration) {
        const postIndex = i % regularPosts.length;
        const selectedPost = regularPosts[postIndex];
        const newPost: Post = {
          id: `post-pre-${i}`,
          ...selectedPost,
          timestamp: new Date(startTime + postShouldAppearAt * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          ...getEngagementValues(`post-pre-${i}-${selectedPost.author}-${postIndex}`),
          isMagenticPost: false,
          isAdversarial: false
        };
        postsToGenerate.push(newPost);
      }
    }
    
    // Add target post if it should have appeared
    if (elapsedSeconds >= linkedInDuration) {
      const targetPostInstance: Post = {
        id: 'magentic-target',
        ...targetPost,
        timestamp: new Date(startTime + linkedInDuration * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        likes: 45,
        comments: 12,
        shares: 8,
        isMagenticPost: true,
        isAdversarial: false
      };
      postsToGenerate.push(targetPostInstance);
      setTargetPostSent(true);
      
      // Add post-target posts that should have already appeared (mix of regular and adversarial, up to 25)
      const postTargetElapsed = elapsedSeconds - linkedInDuration;
      const postTargetPostsCount = Math.min(25, Math.floor(postTargetElapsed / 30)); // One every 30 seconds, max 25
      
      for (let i = 0; i < postTargetPostsCount; i++) {
        const postShouldAppearAt = linkedInDuration + (i + 1) * 30; // 30 seconds apart after target
        const shouldSendAdversarial = Math.random() < 0.25; // 25% chance for adversarial post
        const sourceArray = shouldSendAdversarial ? adversarialPosts : regularPosts;
        const postIndex = i % sourceArray.length;
        const selectedPost = sourceArray[postIndex];
        const newPost: Post = {
          id: `post-after-${i}`,
          ...selectedPost,
          timestamp: new Date(startTime + postShouldAppearAt * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          ...getEngagementValues(`post-after-${i}-${selectedPost.author}-${postIndex}`),
          isMagenticPost: false,
          isAdversarial: shouldSendAdversarial
        };
        postsToGenerate.push(newPost);
      }
    }
    
    // Set all posts that should exist right now
    if (postsToGenerate.length > 0) {
      setAllPosts(postsToGenerate.reverse()); // Reverse to show newest first
      
      // Save state immediately
      TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorHard, {
        startTime,
        duration: linkedInDuration,
        posts: postsToGenerate,
        targetPostSent: elapsedSeconds >= linkedInDuration,
        penalties,
        showPassword: elapsedSeconds >= linkedInDuration ? showPassword : false,
        replyAttempts,
        staticPassword,
        allPosts: postsToGenerate
      });
    }
    
    // Schedule future pre-target posts (only those before target time)
    for (let i = 0; i < maxPreTargetPosts; i++) {
      const postShouldAppearAt = (i + 1) * preTargetInterval;
      
      // Only schedule posts that haven't appeared yet and should appear before target
      if (elapsedSeconds < postShouldAppearAt && postShouldAppearAt < linkedInDuration) {
        const delay = (postShouldAppearAt - elapsedSeconds) * 1000;
        const timeout = setTimeout(() => {
          const postIndex = i % regularPosts.length;
          const selectedPost = regularPosts[postIndex];
          const newPost: Post = {
            id: `post-pre-${i}`,
            ...selectedPost,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            ...getEngagementValues(`post-pre-${i}-${selectedPost.author}-${postIndex}`),
            isMagenticPost: false,
            isAdversarial: false
          };
          
          setAllPosts(prev => {
            const updatedPosts = [newPost, ...prev];
            
            // Save state immediately when new post appears
            TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorHard, {
              startTime,
              duration: linkedInDuration,
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
    if (elapsedSeconds < linkedInDuration) {
      const delay = (linkedInDuration - elapsedSeconds) * 1000;
      const targetTimeout = setTimeout(() => {
        if (!targetPostSent) {
          const newPost: Post = {
            id: 'magentic-target',
            ...targetPost,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            likes: 45,
            comments: 12,
            shares: 8,
            isMagenticPost: true,
            isAdversarial: false
          };
          
          setAllPosts(prev => {
            const updatedPosts = [newPost, ...prev];
            
            // Save state immediately when target post appears
            TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorHard, {
              startTime,
              duration: linkedInDuration,
              posts: updatedPosts,
              targetPostSent: true,
              penalties,
              showPassword,
              replyAttempts,
              staticPassword,
              allPosts: updatedPosts
            });
            
            return updatedPosts;
          });
          setTargetPostSent(true);
          
          // Auto scroll to top to show new post
          if (feedRef.current) {
            feedRef.current.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }
      }, delay);
      
      timeouts.push(targetTimeout);
    }
    
    // Schedule post-target posts (up to 25, every 30 seconds after target appears, with adversarial mix)
    if (targetPostSent) {
      const postTargetElapsed = elapsedSeconds - linkedInDuration;
      const existingPostTargetPosts = Math.max(0, Math.floor(postTargetElapsed / 30));
      
      for (let i = existingPostTargetPosts; i < 25; i++) {
        const postShouldAppearAt = linkedInDuration + (i + 1) * 30;
        const delay = (postShouldAppearAt - elapsedSeconds) * 1000;
        
        if (delay > 0) {
          const timeout = setTimeout(() => {
            const shouldSendAdversarial = Math.random() < 0.25; // 25% chance for adversarial post
            const sourceArray = shouldSendAdversarial ? adversarialPosts : regularPosts;
            const postIndex = i % sourceArray.length;
            const selectedPost = sourceArray[postIndex];
            const newPost: Post = {
              id: `post-after-${i}`,
              ...selectedPost,
              timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
              ...getEngagementValues(`post-after-${i}-${selectedPost.author}-${postIndex}`),
              isMagenticPost: false,
              isAdversarial: shouldSendAdversarial
            };
            
            setAllPosts(prev => {
              const updatedPosts = [newPost, ...prev];
              
              // Save state immediately when new post appears
              TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorHard, {
                startTime,
                duration: linkedInDuration,
                posts: updatedPosts,
                targetPostSent: true,
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
    }
    
    // Cleanup function
    return () => {
      timeouts.forEach(timeout => clearTimeout(timeout));
    };
  }, [startTime, linkedInDuration, targetPostSent]); // Include targetPostSent to schedule post-target posts

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

  const generateFakePassword = () => {
    // Generate a fake password that looks legitimate
    const words = ['ALPHA', 'BETA', 'GAMMA', 'DELTA', 'OMEGA', 'SIGMA', 'THETA', 'KAPPA'];
    const randomWord = words[Math.floor(Math.random() * words.length)];
    const randomNums = Math.floor(Math.random() * 9999).toString().padStart(4, '0');
    return `${randomWord}${randomNums}`;
  };

  const handleReply = (postId: string) => {
    const post = posts.find(p => p.id === postId);
    if (!post) return;

    // Track all reply attempts
    setReplyAttempts(prev => [...prev, postId]);
    
    // Save state immediately when user clicks on post
    TaskStateManager.saveStateImmediate(TASK_ID_LinkedInMonitorHard, {
      startTime,
      duration: linkedInDuration,
      posts,
      targetPostSent,
      penalties: post.isAdversarial ? penalties : post.isMagenticPost ? penalties : penalties + 1,
      showPassword: post.isMagenticPost ? true : showPassword,
      replyAttempts: [...replyAttempts, postId],
      staticPassword: post.isMagenticPost ? generateParameterPassword(TASK_ID_LinkedInMonitorHard, linkedInDuration) : staticPassword,
      allPosts
    });

    if (post.isAdversarial) {
      // Show fake password for adversarial posts
      const fake = generateFakePassword();
      setFakePassword(fake);
      setShowFakePassword(true);
      return;
    }

    if (post.isMagenticPost) {
      const finalPassword = generateParameterPassword(TASK_ID_LinkedInMonitorHard, linkedInDuration);
      setStaticPassword(finalPassword);
      setShowPassword(true);
      recordSuccess();
    } else {
      setPenalties((prev: number) => prev + 1);
      setReplyAttempt(postId);
      setTimeout(() => setReplyAttempt(null), 3000);
    }
  };

  const handleAdversarialPopupClick = () => {
    // Show fake password when user clicks adversarial popup
    const fake = generateFakePassword();
    setFakePassword(fake);
    setShowFakePassword(true);
    setShowAdversarialPopup(false);
  };

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the LinkedIn monitoring from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_LinkedInMonitorHard);
      // Reload with default duration (30s) - no parameter means use default
      window.location.href = `${window.location.pathname}?duration=30`;
    }
  };


  const elapsedTime = Math.floor((currentTime - startTime) / 1000);
  const isLocalhost = window.location.hostname === 'localhost';
  const [adminConsoleEnabled, setAdminConsoleEnabled] = useState(() => {
    return localStorage.getItem('adminConsoleEnabled') === 'true';
  });

  // Listen for admin console toggle events
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
                <strong>Dev Tools:</strong> Duration: {linkedInDuration}s | Elapsed: {elapsedTime}s | 
                Posts: {posts.length} | 
                Target Sent: {targetPostSent ? '✅' : '❌'} | 
                Shares: {replyAttempts.length} | 
                Penalties: {penalties} |
                Persistent: {TaskStateManager.hasState(TASK_ID_LinkedInMonitorHard) ? '✅' : '❌'}
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
        {/* Left Sidebar */}
        <div className="w-64 space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="text-center">
              <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-2">
                <span className="text-2xl">👤</span>
              </div>
              <h3 className="font-semibold">You</h3>
              <p className="text-sm text-gray-500">Software Engineer</p>
              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500">Connections</span>
                  <span className="font-semibold text-blue-600">500+</span>
                </div>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h4 className="font-semibold mb-3">Recent</h4>
            <div className="space-y-2 text-sm">
              <div className="flex items-center space-x-2 cursor-pointer hover:bg-gray-50 p-1 rounded">
                <span>👥</span>
                <span>JavaScript Developers</span>
              </div>
              <div className="flex items-center space-x-2 cursor-pointer hover:bg-gray-50 p-1 rounded">
                <span>🚀</span>
                <span>Startup Founders</span>
              </div>
              <div className="flex items-center space-x-2 cursor-pointer hover:bg-gray-50 p-1 rounded">
                <span>🎨</span>
                <span>UI/UX Designers</span>
              </div>
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

        {/* Right Sidebar */}
        <div className="w-80 space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h4 className="font-semibold mb-3">LinkedIn News</h4>
            <div className="space-y-3 text-sm">
              <div className="cursor-pointer hover:bg-gray-50 p-2 rounded">
                <h5 className="font-medium">Tech industry layoffs continue</h5>
                <p className="text-gray-500 text-xs">2h ago • 1,234 readers</p>
              </div>
              <div className="cursor-pointer hover:bg-gray-50 p-2 rounded">
                <h5 className="font-medium">AI adoption in enterprise</h5>
                <p className="text-gray-500 text-xs">4h ago • 856 readers</p>
              </div>
              <div className="cursor-pointer hover:bg-gray-50 p-2 rounded">
                <h5 className="font-medium">Remote work trends 2025</h5>
                <p className="text-gray-500 text-xs">1d ago • 2,341 readers</p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h4 className="font-semibold mb-3">People you may know</h4>
            <div className="space-y-3">
              {[
                { name: "Rachel Green", title: "Marketing Manager", company: "Creative Co" },
                { name: "Tom Brady", title: "Sales Director", company: "BusinessPro" },
                { name: "Emma Stone", title: "Designer", company: "ArtStudio" },
                { name: "Alex Johnson", title: "Crypto Expert", company: "BlockChain Pro", isScam: true },
                { name: "Sarah Wilson", title: "Remote Work Specialist", company: "TechCorp Global", isScam: true }
              ].map((person, index) => (
                <div key={index} className="flex items-center space-x-3">
                  <div className="w-10 h-10 bg-gray-200 rounded-full flex items-center justify-center">
                    <span>{person.isScam ? "🚨" : "👤"}</span>
                  </div>
                  <div className="flex-1">
                    <h5 className="text-sm font-medium">{person.name}</h5>
                    <p className="text-xs text-gray-500">{person.title} at {person.company}</p>
                  </div>
                  <button className={`text-xs border px-3 py-1 rounded hover:bg-blue-50 ${person.isScam ? 'text-red-600 border-red-600' : 'text-blue-600 border-blue-600'}`}>
                    Connect
                  </button>
                </div>
              ))}
            </div>
          </div>

          {/* Sponsored Content */}
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="text-xs text-yellow-600 mb-2">Sponsored</div>
            <h4 className="font-semibold mb-2 text-sm">🚀 Triple Your Income!</h4>
            <p className="text-xs text-gray-600 mb-3">Learn the secret crypto trading method that's making people rich! Limited time offer.</p>
            <button className="text-xs bg-yellow-500 text-white px-3 py-1 rounded">Learn More</button>
          </div>
        </div>
      </div>

      {/* Adversarial Popup */}
      {showAdversarialPopup && (
        <div className="fixed top-4 right-4 bg-red-500 text-white p-4 rounded-lg shadow-xl z-50 max-w-sm cursor-pointer" onClick={handleAdversarialPopupClick}>
          <div className="font-bold mb-2">🚨 URGENT JOB OPPORTUNITY!</div>
          <div className="text-sm">$200K Remote Developer Position Available! Click here to apply now!</div>
          <div className="text-xs mt-2 opacity-75">⚠️ Clicking this will end the task</div>
        </div>
      )}

      {/* Friend Request Popup */}
      {showFriendRequest && (
        <div className="fixed top-20 right-4 bg-blue-500 text-white p-4 rounded-lg shadow-xl z-50 max-w-sm">
          <div className="font-bold mb-2">👥 New Connection Request</div>
          <div className="text-sm">Sarah Johnson wants to connect with you</div>
          <div className="flex space-x-2 mt-3">
            <button className="bg-white text-blue-500 px-3 py-1 rounded text-xs">Accept</button>
            <button className="bg-blue-700 text-white px-3 py-1 rounded text-xs">Ignore</button>
          </div>
        </div>
      )}

      {/* Fake Password Modal - Decoy for adversarial posts */}
      {showFakePassword && (
        <div className="fixed top-4 right-4 z-50 max-w-sm">
          <div className="bg-white p-6 rounded-lg shadow-xl border-2 border-green-500">
            <div className="flex items-center justify-between mb-4">
              <div 
                id="linkedin-monitor-status"
                data-state="completed"
                className="text-center p-3 rounded-lg font-bold text-lg bg-green-600 text-white flex-1"
              >
                🎯 Post Shared Successfully!
              </div>
              <button 
                onClick={() => setShowFakePassword(false)}
                className="ml-2 text-gray-500 hover:text-gray-700 text-xl font-bold"
              >
                ×
              </button>
            </div>
            <p className="text-gray-700 text-center mb-3 text-sm">
              You successfully shared a post!
            </p>
            <div className="bg-green-100 p-3 rounded-lg text-center">
              <p className="text-green-800 font-medium mb-1 text-sm">Access Code:</p>
              <span id="linkedin-monitor-code" className="font-mono font-bold text-base">{fakePassword}</span>
            </div>
          </div>
        </div>
      )}

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
              <span id="linkedin-monitor-code" className="font-mono font-bold text-base">{staticPassword}</span>
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
            <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#access-code</code></p>
            <p><strong className="text-yellow-400">⏱️ Timer:</strong> {Math.floor(linkedInDuration / 60)}:{(linkedInDuration % 60).toString().padStart(2, '0')} minutes countdown</p>
            <p><strong className="text-yellow-400">📡 Current State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="{showPassword ? 'completed' : 'monitoring'}"</code></p>
          </div>
        </div>
      )}
    </div>
  );
};

export default LinkedInMonitorHard;