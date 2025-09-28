import { useState, useEffect, useRef } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_ScholarWatcherMedium = "scholar-watcher-medium";

interface Paper {
  id: string;
  title: string;
  authors: string;
  journal: string;
  year: number;
  citations: number;
  url: string;
  isTargetPaper: boolean;
}

const ScholarWatcherMedium = () => {
  // Parse URL parameters manually (don't clean yet)
  const urlParams = new URLSearchParams(window.location.search);
  const duration = parseInt(urlParams.get('duration') || DURATION.DEFAULT.toString(), 10);
  const showHints = urlParams.get('hints') === 'true';
  
  // Validate duration parameter
  const taskDuration = (duration >= 1 && duration <= 86400) ? duration : DURATION.DEFAULT;
  
  // Check if validation failed and emit error for toast
  useEffect(() => {
    if (urlParams.has('duration') && taskDuration !== duration) {
      const errors = [{
        parameter: 'duration',
        providedValue: urlParams.get('duration') || '',
        defaultUsed: DURATION.DEFAULT,
        reason: duration < 1 ? 'Value must be at least 1' : 
                duration > 86400 ? 'Value must be at most 86,400' :
                isNaN(duration) ? 'Value must be a valid number' : 'Invalid value'
      }];
      
      setTimeout(() => {
        URLParameterHandler.emitValidationError(errors);
      }, 100);
    }
  }, []); // Run once on mount
  
  // Create params object for shouldResetState check
  const params = { duration: taskDuration, hasAnyParams: urlParams.has('duration') };

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_ScholarWatcherMedium);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_ScholarWatcherMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_ScholarWatcherMedium);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        targetCitations: 1000,
        currentCitations: 85,
        showPassword: false,
        targetPaperReached: false,
        clickedPapers: [] as string[],
        searchQuery: "",
        staticPassword: generateParameterPassword(TASK_ID_ScholarWatcherMedium, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_ScholarWatcherMedium, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        targetCitations: (savedState.targetCitations as number) || 1000,
        currentCitations: (savedState.currentCitations as number) || 85,
        showPassword: savedState.showPassword === true,
        targetPaperReached: savedState.targetPaperReached === true,
        clickedPapers: (savedState.clickedPapers as string[]) || [],
        searchQuery: (savedState.searchQuery as string) || "",
        staticPassword: generateParameterPassword(TASK_ID_ScholarWatcherMedium, savedDuration)
      };
    } else {
      // Fresh start - same as reset case
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        targetCitations: 1000,
        currentCitations: 85,
        showPassword: false,
        targetPaperReached: false,
        clickedPapers: [] as string[],
        searchQuery: "",
        staticPassword: generateParameterPassword(TASK_ID_ScholarWatcherMedium, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_ScholarWatcherMedium, initialState);
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
  const [scholarDuration] = useState(initialState.duration);
  const [targetCitations] = useState(initialState.targetCitations);
  const [currentCitations, setCurrentCitations] = useState(initialState.currentCitations);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [targetPaperReached, setTargetPaperReached] = useState(initialState.targetPaperReached);
  const [clickedPapers, setClickedPapers] = useState(initialState.clickedPapers);
  const [searchQuery, setSearchQuery] = useState(initialState.searchQuery);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [currentTime, setCurrentTime] = useState(Date.now());
  const timerRef = useRef<number | null>(null);
  const { recordSuccess } = useTaskAnalytics(TASK_ID_ScholarWatcherMedium);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.targetPaperReached && initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.targetPaperReached, initialState.showPassword, recordSuccess]);

  // Update current time every second for live elapsed time display
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

  // Papers dataset
  const papers: Paper[] = [
    {
      id: "1",
      title: "Attention Is All You Need",
      authors: "A Vaswani, N Shazeer, N Parmar, J Uszkoreit, L Jones, AN Gomez, L Kaiser, I Polosukhin",
      journal: "Advances in neural information processing systems",
      year: 2017,
      citations: 45237,
      url: "https://arxiv.org/abs/1706.03762",
      isTargetPaper: false
    },
    {
      id: "2", 
      title: "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
      authors: "J Devlin, MW Chang, K Lee, K Toutanova",
      journal: "NAACL-HLT",
      year: 2019,
      citations: 32156,
      url: "https://arxiv.org/abs/1810.04805",
      isTargetPaper: false
    },
    {
      id: "target",
      title: "Neural Machine Translation by Jointly Learning to Align and Translate",
      authors: "D Bahdanau, K Cho, Y Bengio",
      journal: "arXiv preprint arXiv:1409.0473",
      year: 2014,
      citations: currentCitations,
      url: "https://arxiv.org/abs/1409.0473",
      isTargetPaper: true
    },
    {
      id: "3",
      title: "Language Models are Unsupervised Multitask Learners",
      authors: "A Radford, J Wu, R Child, D Luan, D Amodei, I Sutskever",
      journal: "OpenAI blog",
      year: 2019,
      citations: 8942,
      url: "https://d4mucfpksywv.cloudfront.net/better-language-models/language-models.pdf",
      isTargetPaper: false
    },
    {
      id: "4",
      title: "Deep Residual Learning for Image Recognition",
      authors: "K He, X Zhang, S Ren, J Sun",
      journal: "Proceedings of the IEEE conference on computer vision and pattern recognition",
      year: 2016,
      citations: 89234,
      url: "https://arxiv.org/abs/1512.03385",
      isTargetPaper: false
    },
    {
      id: "5",
      title: "Generative Adversarial Nets",
      authors: "I Goodfellow, J Pouget-Abadie, M Mirza, B Xu, D Warde-Farley, S Ozair, A Courville, Y Bengio",
      journal: "Advances in neural information processing systems",
      year: 2014,
      citations: 43821,
      url: "https://arxiv.org/abs/1406.2661",
      isTargetPaper: false
    },
    {
      id: "6",
      title: "Adam: A Method for Stochastic Optimization", 
      authors: "DP Kingma, J Ba",
      journal: "arXiv preprint arXiv:1412.6980",
      year: 2014,
      citations: 67432,
      url: "https://arxiv.org/abs/1412.6980",
      isTargetPaper: false
    },
    {
      id: "7",
      title: "ImageNet Classification with Deep Convolutional Neural Networks",
      authors: "A Krizhevsky, I Sutskever, GE Hinton",
      journal: "Communications of the ACM",
      year: 2017,
      citations: 98765,
      url: "https://dl.acm.org/doi/10.1145/3065386",
      isTargetPaper: false
    }
  ];

  // Citation growth algorithm (S-curve to reach target over duration)
  const calculateCitations = (elapsedSeconds: number) => {
    const initialCitations = 85;
    const progress = Math.min(elapsedSeconds / scholarDuration, 1);
    
    // S-curve function
    const k = 8; // steepness
    const midPoint = 0.6; // 60% through duration
    const normalizedTime = k * (progress - midPoint);
    const sigmoidValue = 1 / (1 + Math.exp(-normalizedTime));
    
    const citationCount = Math.round(initialCitations + (targetCitations - initialCitations) * sigmoidValue);
    return Math.min(citationCount, targetCitations);
  };

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: scholarDuration,
      targetCitations,
      currentCitations,
      showPassword,
      targetPaperReached,
      clickedPapers,
      searchQuery,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_ScholarWatcherMedium, currentState);
  }, [startTime, scholarDuration, targetCitations, currentCitations, showPassword, targetPaperReached, clickedPapers, searchQuery, staticPassword]);

  // Update citations over time
  useEffect(() => {
    const interval = setInterval(() => {
      const elapsedSeconds = (Date.now() - startTime) / 1000;
      const newCitations = calculateCitations(elapsedSeconds);
      
      setCurrentCitations(newCitations);
      
      // Check if target citations reached
      if (newCitations >= targetCitations && !targetPaperReached) {
        setTargetPaperReached(true);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [startTime, scholarDuration, targetCitations, targetPaperReached]);

  const handlePaperClick = (paperId: string) => {
    const paper = papers.find(p => p.id === paperId);
    if (!paper) return;

    // Track clicked papers
    setClickedPapers(prev => [...prev, paperId]);
    
    if (paper.isTargetPaper && targetPaperReached) {
      // Success! Target paper clicked after reaching target citations
      const finalPassword = generateParameterPassword(TASK_ID_ScholarWatcherMedium, scholarDuration);
      setStaticPassword(finalPassword);
      setShowPassword(true);
      recordSuccess();
    }
  };

  const handleSearchChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(event.target.value);
  };

  // Filter papers based on search query
  const filteredPapers = searchQuery.trim() 
    ? papers.filter(paper => 
        paper.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        paper.authors.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : papers;

  // Update target paper citations in the dataset
  const papersWithUpdatedCitations = filteredPapers.map(paper => 
    paper.isTargetPaper ? { ...paper, citations: currentCitations } : paper
  );

  const handleResetTask = () => {
    if (window.confirm('Are you sure you want to reset this task? This will restart the citation monitoring from the beginning.')) {
      TaskStateManager.clearState(TASK_ID_ScholarWatcherMedium);
      window.location.reload();
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
    const handleAdminConsoleToggle = (e: CustomEvent) => {
      setAdminConsoleEnabled(e.detail.enabled);
    };

    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'adminConsoleEnabled') {
        setAdminConsoleEnabled(e.newValue === 'true');
      }
    };

    const syncWithStorage = () => {
      const currentValue = localStorage.getItem('adminConsoleEnabled') === 'true';
      setAdminConsoleEnabled(currentValue);
    };

    window.addEventListener('adminConsoleToggle', handleAdminConsoleToggle as EventListener);
    window.addEventListener('storage', handleStorageChange);
    
    // Sync every 2 seconds in case localStorage changes from another tab
    const interval = setInterval(syncWithStorage, 2000);

    return () => {
      window.removeEventListener('adminConsoleToggle', handleAdminConsoleToggle as EventListener);
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 rounded-xl p-4 mb-6 mx-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Duration: {scholarDuration}s | 
              Elapsed: {elapsedTime}s | 
              Citations: {currentCitations}/{targetCitations} | 
              Target Reached: {targetPaperReached ? '✅' : '❌'} |
              Persistent: {TaskStateManager.hasState(TASK_ID_ScholarWatcherMedium) ? '✅' : '❌'}
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

      {/* Google Scholar Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center space-x-8">
            <div className="flex items-center space-x-3">
              <div className="text-3xl font-bold">
                <span className="text-blue-500">G</span>
                <span className="text-red-500">o</span>
                <span className="text-yellow-500">o</span>
                <span className="text-blue-500">g</span>
                <span className="text-green-500">l</span>
                <span className="text-red-500">e</span>
              </div>
              <span className="text-2xl font-normal text-gray-700">Scholar</span>
            </div>
            
            <div className="flex-1 max-w-2xl">
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search articles, case law, patents, citations, and more"
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="w-full px-4 py-3 text-lg border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent shadow-sm"
                />
                <button className="absolute right-3 top-1/2 transform -translate-y-1/2 p-2 text-gray-500 hover:text-gray-700">
                  🔍
                </button>
              </div>
            </div>

            <nav className="flex items-center space-x-6 text-sm">
              <a href="#" className="text-blue-600 hover:underline">My library</a>
              <a href="#" className="text-blue-600 hover:underline">Alerts</a>
              <a href="#" className="text-blue-600 hover:underline">Settings</a>
              <button className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">Sign in</button>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Search Results Header */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-lg font-normal text-gray-700">
              About {papersWithUpdatedCitations.length.toLocaleString()} results ({(Math.random() * 0.5 + 0.1).toFixed(2)} sec)
            </h1>
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <select className="border border-gray-300 rounded px-3 py-1">
                <option>Sort by relevance</option>
                <option>Sort by date</option>
                <option>Sort by citation</option>
              </select>
              <div className="flex items-center space-x-2">
                <span>Since 2019</span>
                <span>•</span>
                <span>Any language</span>
              </div>
            </div>
          </div>
        </div>

        {/* Search Results */}
        <div className="space-y-6">
          {papersWithUpdatedCitations.map((paper) => (
            <div key={paper.id} className="bg-white p-6 rounded-lg border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
              <div className="mb-3">
                <h3 
                  className={`text-lg font-medium cursor-pointer hover:underline ${
                    paper.isTargetPaper && targetPaperReached ? 'text-blue-600 animate-pulse' : 'text-blue-600'
                  }`}
                  onClick={() => handlePaperClick(paper.id)}
                >
                  {paper.title}
                </h3>
              </div>
              
              <div className="text-sm text-green-700 mb-2">
                {paper.authors}
              </div>
              
              <div className="text-sm text-gray-600 mb-3">
                {paper.journal}, {paper.year}
              </div>
              
              <div className="text-sm text-gray-700 mb-3">
                {paper.title.includes('Attention') && "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism..."}
                {paper.title.includes('BERT') && "We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers. Unlike recent language representation models, BERT is designed to pre-train deep bidirectional representations..."}
                {paper.title.includes('Neural Machine Translation') && "Neural machine translation is a recently proposed approach to machine translation. Unlike the traditional statistical machine translation, the neural machine translation aims at building a single neural network that can be jointly tuned to maximize the translation performance..."}
                {paper.title.includes('Language Models are') && "Natural language processing tasks, such as question answering, machine comprehension, textual entailment, and summarization, are typically approached with supervised learning on task-specific datasets..."}
                {paper.title.includes('Deep Residual') && "Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously..."}
                {paper.title.includes('Generative Adversarial') && "We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models: a generative model G that captures the data distribution..."}
                {paper.title.includes('Adam') && "We introduce Adam, an algorithm for first-order gradient-based optimization of stochastic objective functions, based on adaptive estimates of lower-order moments..."}
                {paper.title.includes('ImageNet') && "We trained a large, deep convolutional neural network to classify the 1.2 million high-resolution images in the ImageNet LSVRC-2010 contest into the 1000 different classes..."}
              </div>
              
              <div className="flex items-center justify-between text-sm">
                <div className="flex items-center space-x-4 text-gray-600">
                  <span className="font-medium">Cited by {paper.citations.toLocaleString()}</span>
                  <span className="text-blue-600 hover:underline cursor-pointer">Related articles</span>
                  <span className="text-blue-600 hover:underline cursor-pointer">All {Math.floor(Math.random() * 10) + 1} versions</span>
                </div>
                
                <div className="flex items-center space-x-3">
                  <button className="text-blue-600 hover:underline text-xs">Save</button>
                  <button className="text-blue-600 hover:underline text-xs">Cite</button>
                  <button className="text-gray-600 hover:text-gray-800 text-xs">📧</button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Pagination */}
        <div className="mt-8 flex items-center justify-center space-x-2">
          <button className="px-3 py-2 text-blue-600 hover:bg-blue-50 rounded">Previous</button>
          {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((page) => (
            <button 
              key={page}
              className={`px-3 py-2 rounded ${
                page === 1 ? 'bg-blue-600 text-white' : 'text-blue-600 hover:bg-blue-50'
              }`}
            >
              {page}
            </button>
          ))}
          <button className="px-3 py-2 text-blue-600 hover:bg-blue-50 rounded">Next</button>
        </div>
      </div>

      {/* Success Message */}
      {showPassword && (
        <div className="fixed top-4 right-4 bg-white border-l-4 border-green-500 p-6 rounded-lg shadow-xl max-w-sm z-50">
          <div className="flex items-start space-x-3">
            <div className="text-green-500 text-xl">📚</div>
            <div>
              <h3 
                id="scholar-watcher-status"
                data-state="completed"
                className="font-semibold text-gray-900 mb-1"
              >
                Paper Milestone Reached!
              </h3>
              <p className="text-sm text-gray-600 mb-2">
                The paper "Neural Machine Translation by Jointly Learning to Align and Translate" reached {targetCitations} citations!
              </p>
              <div className="bg-green-50 p-3 rounded">
                <p className="text-green-800 font-medium mb-1 text-sm">Access Code:</p>
                <code 
                  id="scholar-watcher-code"
                  className="font-mono font-bold text-sm text-green-700 block"
                >
                  {staticPassword || generateParameterPassword(TASK_ID_ScholarWatcherMedium, scholarDuration)}
                </code>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Technical Details */}
      {showHints && (
        <div className="max-w-7xl mx-auto px-4 pb-6">
          <div className="bg-gray-900 text-green-400 rounded-lg p-6 border-2 border-green-500 font-mono">
            <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
            <div className="text-sm space-y-2">
              <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#scholar-watcher-status</code></p>
              <p><strong className="text-yellow-400">✅ Completion State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="completed"</code></p>
              <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#scholar-watcher-code</code></p>
              <p><strong className="text-yellow-400">⏱️ Duration:</strong> {Math.floor(scholarDuration / 60)}:{(scholarDuration % 60).toString().padStart(2, '0')} minutes to reach {targetCitations} citations</p>
              <p><strong className="text-yellow-400">📊 Target Paper:</strong> "Neural Machine Translation by Jointly Learning to Align and Translate"</p>
              <p><strong className="text-yellow-400">🎯 Goal:</strong> Wait for target paper to reach {targetCitations} citations, then click on it</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ScholarWatcherMedium;