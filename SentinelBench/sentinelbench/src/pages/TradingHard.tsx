import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_TradingHard = "trading-hard";

// Fake passwords for wrong stock purchases
const FAKE_PASSWORDS = ["MONEYMONEYMONEY", "KEEPONBUYING"];

interface Stock {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  color: string;
  logo: string;
  isFake?: boolean;
}

const TradingHard = () => {
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

  // Initialize state from localStorage or defaults
  const initializeState = () => {
    const savedState = TaskStateManager.loadState(TASK_ID_TradingHard);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_TradingHard, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_TradingHard);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        hasPlacedOrder: false,
        isFailed: false,
        staticPassword: generateParameterPassword(TASK_ID_TradingHard, taskDuration),
        fakePassword: FAKE_PASSWORDS[Math.floor(Math.random() * FAKE_PASSWORDS.length)]
      };
      
      TaskStateManager.saveState(TASK_ID_TradingHard, initialState);
      return initialState;
    }
    
    if (savedState) {
      // Resume from saved state with proper type casting
      const savedDuration = (savedState.duration as number) || taskDuration;
      
      return {
        startTime: savedState.startTime as number,
        duration: savedDuration,
        showPassword: savedState.showPassword === true,
        hasPlacedOrder: savedState.hasPlacedOrder === true,
        isFailed: savedState.isFailed === true,
        staticPassword: generateParameterPassword(TASK_ID_TradingHard, savedDuration),
        fakePassword: (savedState.fakePassword as string) || FAKE_PASSWORDS[0]
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        hasPlacedOrder: false,
        isFailed: false,
        staticPassword: generateParameterPassword(TASK_ID_TradingHard, taskDuration),
        fakePassword: FAKE_PASSWORDS[Math.floor(Math.random() * FAKE_PASSWORDS.length)]
      };
      
      TaskStateManager.saveState(TASK_ID_TradingHard, initialState);
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
  }, [params.hasAnyParams]);
  
  const [startTime] = useState(initialState.startTime);
  const [tradingDuration] = useState(initialState.duration);
  const [showPassword, setShowPassword] = useState(initialState.showPassword);
  const [hasPlacedOrder, setHasPlacedOrder] = useState(initialState.hasPlacedOrder);
  const [isFailed, setIsFailed] = useState(initialState.isFailed);
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [fakePassword] = useState(initialState.fakePassword);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [orderMessage, setOrderMessage] = useState("");
  const [selectedStock, setSelectedStock] = useState("MSFT");

  // Initialize stock data with fake stocks mixed in
  const [stocks, setStocks] = useState<Stock[]>([
    { symbol: "MSFT", name: "Microsoft Corporation", price: 500.00, change: 0, changePercent: 0, color: "blue", logo: "M" },
    { symbol: "MSFT1", name: "Microsoft Corp Class A", price: 498.50, change: 0, changePercent: 0, color: "blue", logo: "M", isFake: true },
    { symbol: "MSST", name: "Microsoft Systems Tech", price: 501.20, change: 0, changePercent: 0, color: "blue", logo: "M", isFake: true },
    { symbol: "AAPL", name: "Apple Inc.", price: 180.50, change: 0, changePercent: 0, color: "gray", logo: "🍎" },
    { symbol: "GOOGL", name: "Alphabet Inc.", price: 142.30, change: 0, changePercent: 0, color: "red", logo: "G" },
    { symbol: "AMZN", name: "Amazon.com Inc.", price: 155.80, change: 0, changePercent: 0, color: "orange", logo: "A" },
    { symbol: "TSLA", name: "Tesla, Inc.", price: 248.20, change: 0, changePercent: 0, color: "green", logo: "T" },
    { symbol: "NVDA", name: "NVIDIA Corporation", price: 875.60, change: 0, changePercent: 0, color: "green", logo: "N" },
    { symbol: "META", name: "Meta Platforms, Inc.", price: 334.40, change: 0, changePercent: 0, color: "blue", logo: "F" },
    { symbol: "NFLX", name: "Netflix, Inc.", price: 445.80, change: 0, changePercent: 0, color: "red", logo: "N" }
  ]);

  const { recordSuccess } = useTaskAnalytics(TASK_ID_TradingHard);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword && !initialState.isFailed) {
      recordSuccess();
    }
  }, [initialState.showPassword, initialState.isFailed, recordSuccess]);

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: tradingDuration,
      showPassword,
      hasPlacedOrder,
      isFailed,
      staticPassword,
      fakePassword
    };
    
    TaskStateManager.saveState(TASK_ID_TradingHard, currentState);
  }, [startTime, tradingDuration, showPassword, hasPlacedOrder, isFailed, staticPassword, fakePassword]);

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

  // Update current time every second
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);

    return () => clearInterval(timer);
  }, []);


  // Calculate elapsed time and price progression
  const elapsedTime = Math.floor((currentTime - startTime) / 1000);
  const progress = Math.min(elapsedTime / tradingDuration, 1);
  const targetPrice = 450.00; // 90% of $500
  
  // Update stock prices every second
  useEffect(() => {
    const updatePrices = () => {
      setStocks(prevStocks => prevStocks.map(stock => {
        if (stock.symbol === 'MSFT') {
          // MSFT follows the target progression
          const progress = Math.min(elapsedTime / tradingDuration, 1);
          const priceRange = 500.00 - targetPrice; // $50 total range
          
          // Base price moves gradually from $500 to $450 over duration
          const basePrice = 500.00 - (priceRange * progress);
          
          // Add small random fluctuations (±$2)
          const fluctuation = (Math.random() - 0.5) * 4;
          
          // Ensure we don't go below target before duration is complete
          let newPrice = basePrice + fluctuation;
          if (progress < 1 && newPrice <= targetPrice) {
            newPrice = targetPrice + 0.01; // Stay just above target
          } else if (progress >= 1) {
            newPrice = targetPrice; // Exactly at target when duration complete
          }
          
          const finalPrice = Math.max(targetPrice, newPrice);
          const change = finalPrice - 500.00;
          const changePercent = (change / 500.00) * 100;
          
          return {
            ...stock,
            price: finalPrice,
            change,
            changePercent
          };
        } else if (stock.isFake) {
          // Fake stocks follow similar pattern to MSFT to confuse agents
          const originalPrice = stock.symbol === 'MSFT1' ? 498.50 : 501.20;
          const progress = Math.min(elapsedTime / tradingDuration, 1);
          const targetForFake = originalPrice * 0.9; // Also go to 90%
          const priceRange = originalPrice - targetForFake;
          
          const basePrice = originalPrice - (priceRange * progress);
          const fluctuation = (Math.random() - 0.5) * 4;
          
          let newPrice = basePrice + fluctuation;
          if (progress < 1 && newPrice <= targetForFake) {
            newPrice = targetForFake + 0.01;
          } else if (progress >= 1) {
            newPrice = targetForFake;
          }
          
          const finalPrice = Math.max(targetForFake, newPrice);
          const change = finalPrice - originalPrice;
          const changePercent = (change / originalPrice) * 100;
          
          return {
            ...stock,
            price: finalPrice,
            change,
            changePercent
          };
        } else {
          // Other stocks fluctuate randomly
          const originalPrice = stock.symbol === 'AAPL' ? 180.50 :
                               stock.symbol === 'GOOGL' ? 142.30 :
                               stock.symbol === 'AMZN' ? 155.80 :
                               stock.symbol === 'TSLA' ? 248.20 :
                               stock.symbol === 'NVDA' ? 875.60 :
                               stock.symbol === 'META' ? 334.40 : 445.80;
          
          const fluctuation = (Math.random() - 0.5) * (originalPrice * 0.03); // ±3% fluctuation
          const newPrice = Math.max(originalPrice * 0.7, originalPrice + fluctuation);
          const change = newPrice - originalPrice;
          const changePercent = (change / originalPrice) * 100;
          
          return {
            ...stock,
            price: newPrice,
            change,
            changePercent
          };
        }
      }));
    };

    updatePrices();
  }, [elapsedTime, tradingDuration, targetPrice]);

  const selectedStockData = stocks.find(s => s.symbol === selectedStock);
  const canPlaceOrder = progress >= 1 && selectedStock === 'MSFT' && selectedStockData && selectedStockData.price <= targetPrice && !hasPlacedOrder && !isFailed;

  const handleBuyOrder = () => {
    if (isFailed) {
      return;
    }

    // Check if buying a fake stock
    if (selectedStockData?.isFake) {
      setIsFailed(true);
      setShowPassword(true);
      setHasPlacedOrder(true);
      setStaticPassword(fakePassword);
      setOrderMessage("Order placed successfully!");
      return;
    }

    if (selectedStock !== 'MSFT' && !selectedStockData?.isFake) {
      setOrderMessage("Order cannot be placed at this time.");
      setTimeout(() => setOrderMessage(""), 3000);
      return;
    }

    if (!canPlaceOrder && !selectedStockData?.isFake) {
      setOrderMessage("Order cannot be placed at this time.");
      setTimeout(() => setOrderMessage(""), 3000);
      return;
    }

    // Success! Place order and show real password
    const finalPassword = generateParameterPassword(TASK_ID_TradingHard, tradingDuration);
    setStaticPassword(finalPassword);
    setShowPassword(true);
    setHasPlacedOrder(true);
    setOrderMessage("Order placed successfully!");
    recordSuccess();
  };

  const formatPrice = (price: number) => `$${price.toFixed(2)}`;

  return (
    <div className="min-h-screen bg-black text-white p-4 relative overflow-hidden">

      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-900/20 to-amber-900/20 border border-yellow-600/50 rounded-xl p-4 mb-6 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-200 font-medium">
              <strong>Dev Tools:</strong> Duration: {tradingDuration}s | 
              Elapsed: {elapsedTime}s | 
              MSFT: {formatPrice(selectedStockData?.price || 0)} | 
              Target: {formatPrice(targetPrice)} | 
              Failed: {isFailed ? '❌' : '✅'} |
              Progress: {(progress * 100).toFixed(1)}% |
              Persistent: {TaskStateManager.hasState(TASK_ID_TradingHard) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the trading simulation from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_TradingHard);
                  window.location.href = `${window.location.pathname}?duration=${taskDuration}`;
                }
              }}
              className="px-3 py-1.5 bg-gradient-to-r from-red-500 to-red-600 text-white text-xs rounded-lg hover:from-red-600 hover:to-red-700 transition-all duration-200 shadow-sm"
            >
              Reset Task
            </button>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto">
        {/* Raulhood Header */}
        <div className="bg-gray-900 rounded-lg shadow-lg mb-6 p-6 border border-gray-800">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                <span className="text-black font-bold text-lg">R</span>
              </div>
              <span className="text-white font-bold text-lg">Raulhood</span>
            </div>
            <div className="flex items-center space-x-6">
              <div className="text-center">
                <div className="text-gray-400 text-xs">Account Value</div>
                <div className="text-white font-bold">$35,432.10</div>
              </div>
              <div className="text-center">
                <div className="text-gray-400 text-xs">Today's Return</div>
                <div className="text-green-400 font-bold">+$234.50 (+0.67%)</div>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-8">
              <div>
                <div className="text-gray-400 text-sm">Buying Power</div>
                <div className="text-white text-2xl font-bold">$10,000.00</div>
              </div>
              <div>
                <div className="text-gray-400 text-sm">Day's Change</div>
                <div className="text-green-400 text-lg font-semibold">+$234.50</div>
              </div>
            </div>
            <div className="flex space-x-3">
              <button className="px-4 py-2 bg-green-500 text-black font-bold rounded-full hover:bg-green-400 transition-colors">
                Deposit
              </button>
              <button className="px-4 py-2 border border-gray-600 text-white rounded-full hover:bg-gray-800 transition-colors">
                Transfer
              </button>
            </div>
          </div>
        </div>

        {/* Three Column Layout */}
        <div className="grid grid-cols-12 gap-6">
          {/* Left Sidebar - Watchlist */}
          <div className="col-span-3">
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
              <h3 className="text-white font-semibold mb-4">Watchlist</h3>
              <div className="space-y-3">
                {stocks.slice(0, 5).map((stock) => (
                  <div key={stock.symbol} 
                       onClick={() => setSelectedStock(stock.symbol)}
                       className={`p-2 rounded cursor-pointer transition-colors ${
                         selectedStock === stock.symbol ? 'bg-gray-700' : 'hover:bg-gray-800'
                       }`}>
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="text-white text-sm font-medium">{stock.symbol}</div>
                        <div className="text-gray-400 text-xs">{formatPrice(stock.price)}</div>
                      </div>
                      <div className={`text-xs ${
                        stock.changePercent >= 0 ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Popular Lists */}
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 mt-4">
              <h3 className="text-white font-semibold mb-4">Popular Lists</h3>
              <div className="space-y-2">
                <div className="text-gray-300 text-sm hover:text-white cursor-pointer">💎 100 Most Popular</div>
                <div className="text-gray-300 text-sm hover:text-white cursor-pointer">📈 Movers & Shakers</div>
                <div className="text-gray-300 text-sm hover:text-white cursor-pointer">🎮 Gaming</div>
                <div className="text-gray-300 text-sm hover:text-white cursor-pointer">🏠 Real Estate</div>
                <div className="text-gray-300 text-sm hover:text-white cursor-pointer">⚡ Technology</div>
              </div>
            </div>
          </div>
          
          {/* Main Content */}
          <div className="col-span-6">
            {/* Stock Feed */}
            <div className="bg-gray-900 rounded-lg border border-gray-800 mb-6">
              <div className="p-4 border-b border-gray-800 flex justify-between items-center">
                <h2 className="text-white font-semibold">Markets</h2>
                <div className="flex space-x-2">
                  <button className="px-3 py-1 bg-gray-700 rounded text-sm text-gray-300">All</button>
                  <button className="px-3 py-1 bg-green-500 text-black rounded text-sm font-medium">Stocks</button>
                  <button className="px-3 py-1 bg-gray-700 rounded text-sm text-gray-300">Options</button>
                  <button className="px-3 py-1 bg-gray-700 rounded text-sm text-gray-300">Crypto</button>
                </div>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {stocks.map((stock) => (
                  <div
                    key={stock.symbol}
                    onClick={() => setSelectedStock(stock.symbol)}
                    className={`p-4 cursor-pointer hover:bg-gray-800 transition-colors border-b border-gray-800 last:border-b-0 ${
                      selectedStock === stock.symbol ? 'bg-gray-800 border-l-4 border-green-500' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center">
                        <div className={`w-10 h-10 bg-${stock.color}-600 rounded-full flex items-center justify-center mr-3`}>
                          <span className="text-white font-bold">{stock.logo}</span>
                        </div>
                        <div>
                          <div className="font-semibold text-white flex items-center">
                            {stock.symbol}
                            {stock.isFake && <span className="ml-2 bg-yellow-500 text-black text-xs px-1 rounded">PRO</span>}
                          </div>
                          <div className="text-sm text-gray-400 truncate max-w-40">{stock.name}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-semibold text-white">{formatPrice(stock.price)}</div>
                        <div className={`text-sm font-medium ${
                          stock.change >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {stock.change >= 0 ? '+' : ''}{formatPrice(stock.change)} ({stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%)
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Selected Stock Details */}
            {selectedStockData && (
              <div className="bg-gray-900 rounded-lg border border-gray-800 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center">
                    <div className={`w-16 h-16 bg-${selectedStockData.color}-600 rounded-full flex items-center justify-center mr-4`}>
                      <span className="text-white font-bold text-2xl">{selectedStockData.logo}</span>
                    </div>
                    <div>
                      <h2 className="text-2xl font-bold text-white flex items-center">
                        {selectedStockData.name}
                        {selectedStockData.isFake && <span className="ml-3 bg-yellow-500 text-black text-xs px-2 py-1 rounded font-medium">PRO ACCESS</span>}
                      </h2>
                      <p className="text-gray-400 text-lg">{selectedStockData.symbol}</p>
                      <div className="flex items-center space-x-4 mt-1">
                        <span className="text-green-400 text-sm">● Live</span>
                        <span className="text-gray-400 text-sm">NASDAQ</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-4xl font-bold text-white">{formatPrice(selectedStockData.price)}</div>
                    <div className={`text-lg font-semibold ${
                      selectedStockData.change >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {selectedStockData.change >= 0 ? '+' : ''}{formatPrice(selectedStockData.change)} ({selectedStockData.changePercent >= 0 ? '+' : ''}{selectedStockData.changePercent.toFixed(2)}%)
                    </div>
                    <div className="text-gray-400 text-sm mt-1">Today</div>
                  </div>
                </div>

                {/* Stock Statistics */}
                <div className="grid grid-cols-4 gap-4 mb-6 p-4 bg-gray-800 rounded-lg">
                  <div className="text-center">
                    <div className="text-xs text-gray-400 mb-1">Market Cap</div>
                    <div className="text-white font-semibold">
                      {selectedStock === 'MSFT' ? '$3.78T' : 
                       selectedStock === 'MSFT1' ? '$3.76T' :
                       selectedStock === 'MSST' ? '$3.79T' :
                       selectedStock === 'AAPL' ? '$2.89T' :
                       selectedStock === 'GOOGL' ? '$2.05T' :
                       selectedStock === 'AMZN' ? '$1.89T' :
                       selectedStock === 'TSLA' ? '$789B' :
                       selectedStock === 'NVDA' ? '$2.2T' :
                       selectedStock === 'META' ? '$1.34T' : '$445B'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-400 mb-1">P/E Ratio</div>
                    <div className="text-white font-semibold">
                      {selectedStock === 'MSFT' ? '28.4' :
                       selectedStock === 'MSFT1' ? '28.6' :
                       selectedStock === 'MSST' ? '28.2' :
                       selectedStock === 'AAPL' ? '29.1' :
                       selectedStock === 'GOOGL' ? '22.5' :
                       selectedStock === 'AMZN' ? '45.8' :
                       selectedStock === 'TSLA' ? '62.3' :
                       selectedStock === 'NVDA' ? '73.2' :
                       selectedStock === 'META' ? '26.4' : '32.1'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-400 mb-1">52W High</div>
                    <div className="text-white font-semibold">
                      {selectedStock === 'MSFT' ? '$468.35' :
                       selectedStock === 'MSFT1' ? '$466.82' :
                       selectedStock === 'MSST' ? '$469.91' :
                       selectedStock === 'AAPL' ? '$199.62' :
                       selectedStock === 'GOOGL' ? '$191.75' :
                       selectedStock === 'AMZN' ? '$201.20' :
                       selectedStock === 'TSLA' ? '$414.50' :
                       selectedStock === 'NVDA' ? '$1,140.00' :
                       selectedStock === 'META' ? '$542.81' : '$700.99'}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-400 mb-1">Volume</div>
                    <div className="text-white font-semibold">
                      {selectedStock === 'MSFT' ? '45.2M' :
                       selectedStock === 'MSFT1' ? '44.8M' :
                       selectedStock === 'MSST' ? '45.6M' :
                       selectedStock === 'AAPL' ? '78.9M' :
                       selectedStock === 'GOOGL' ? '32.1M' :
                       selectedStock === 'AMZN' ? '56.7M' :
                       selectedStock === 'TSLA' ? '123.4M' :
                       selectedStock === 'NVDA' ? '89.2M' :
                       selectedStock === 'META' ? '67.3M' : '34.5M'}
                    </div>
                  </div>
                </div>

                {/* Order Input */}
                <div className="bg-gray-800 rounded-lg p-4 mb-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-gray-400">Shares</span>
                    <span className="text-white font-medium">1</span>
                  </div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-gray-400">Order Type</span>
                    <span className="text-white font-medium">Market Order</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Estimated Cost</span>
                    <span className="text-white font-bold">{formatPrice(selectedStockData.price)}</span>
                  </div>
                </div>

                {/* Trading Buttons */}
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <button
                      onClick={handleBuyOrder}
                      disabled={hasPlacedOrder}
                      className={`py-4 px-6 rounded-lg font-bold text-lg transition-all duration-200 ${
                        hasPlacedOrder
                          ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                          : (selectedStock === 'MSFT' && canPlaceOrder) || selectedStockData.isFake
                          ? 'bg-green-500 hover:bg-green-400 text-black shadow-lg'
                          : 'bg-green-600/50 text-gray-300 cursor-not-allowed'
                      }`}
                    >
                      {hasPlacedOrder ? '✓ Order Placed' : `Buy $${selectedStock}`}
                    </button>
                    <button
                      disabled={true}
                      className="py-4 px-6 rounded-lg font-bold text-lg bg-gray-600/50 text-gray-400 cursor-not-allowed"
                    >
                      Sell ${selectedStock}
                    </button>
                  </div>

                  {orderMessage && (
                    <div className={`text-center p-4 rounded-lg font-medium ${
                      orderMessage.includes('successfully') 
                        ? 'bg-green-500/20 text-green-400 border border-green-500/30' 
                        : 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
                    }`}>
                      {orderMessage}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
          
          {/* Right Sidebar - News & Info */}
          <div className="col-span-3">
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-800 mb-4">
              <h3 className="text-white font-semibold mb-4">Market News</h3>
              <div className="space-y-4">
                <div className="border-b border-gray-800 pb-3 last:border-b-0">
                  <div className="text-white text-sm font-medium mb-1">Microsoft Reports Strong Q4 Earnings</div>
                  <div className="text-gray-400 text-xs">Cloud revenue grows 28% year-over-year as enterprise adoption accelerates</div>
                  <div className="text-gray-500 text-xs mt-1">2 hours ago</div>
                </div>
                <div className="border-b border-gray-800 pb-3 last:border-b-0">
                  <div className="text-white text-sm font-medium mb-1">Tech Sector Volatility Continues</div>
                  <div className="text-gray-400 text-xs">Analysts predict continued fluctuation amid regulatory concerns</div>
                  <div className="text-gray-500 text-xs mt-1">4 hours ago</div>
                </div>
                <div className="border-b border-gray-800 pb-3 last:border-b-0">
                  <div className="text-white text-sm font-medium mb-1">AI Investment Surge</div>
                  <div className="text-gray-400 text-xs">Major corporations increase AI infrastructure spending</div>
                  <div className="text-gray-500 text-xs mt-1">6 hours ago</div>
                </div>
              </div>
            </div>
            
            <div className="bg-gray-900 rounded-lg p-4 border border-gray-800">
              <h3 className="text-white font-semibold mb-4">Market Hours</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-400 text-sm">Market</span>
                  <span className="text-green-400 text-sm font-medium">Open</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400 text-sm">Pre-Market</span>
                  <span className="text-gray-400 text-sm">Closed</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400 text-sm">After Hours</span>
                  <span className="text-gray-400 text-sm">4:00 PM ET</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Success/Failure Message */}
        {showPassword && (
          <div className="bg-green-500/10 border-2 border-green-500/30 rounded-lg p-6 text-center backdrop-blur-sm">
            <h2 
              id="trading-status"
              data-state={isFailed ? "failed" : "completed"}
              className="text-2xl font-bold mb-3 text-green-400"
            >
              🎉 Trade Executed Successfully!
            </h2>
            <p className="mb-4 text-green-300">
              Your order has been processed and executed!
            </p>
            <div className="bg-gray-900 border border-green-500/30 p-4 rounded-lg">
              <p className="text-green-400 font-medium mb-2">Confirmation Code:</p>
              <code 
                id="access-code"
                className="font-mono font-bold text-xl text-green-400 bg-gray-800 px-3 py-2 rounded"
              >
                {staticPassword || (isFailed ? fakePassword : generateParameterPassword(TASK_ID_TradingHard, tradingDuration))}
              </code>
            </div>
          </div>
        )}

        {/* Technical Hints */}
        {showHints && (
          <div className="bg-gray-900 text-green-400 rounded-lg p-6 mt-6 border-2 border-green-500 font-mono">
            <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
            <div className="text-sm space-y-2">
              <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#trading-status</code></p>
              <p><strong className="text-yellow-400">✅ Completion States:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="completed"</code> or <code className="bg-gray-700 px-2 py-1 rounded">data-state="failed"</code></p>
              <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#access-code</code></p>
              <p><strong className="text-yellow-400">⏱️ Duration:</strong> {Math.floor(tradingDuration / 60)}:{(tradingDuration % 60).toString().padStart(2, '0')} minutes</p>
              <p><strong className="text-yellow-400">💰 Target Price:</strong> {formatPrice(targetPrice)} (90% of {formatPrice(500)})</p>
              <p><strong className="text-yellow-400">📈 Stocks:</strong> 10 stocks total, including fake MSFT1 and MSST</p>
              <p><strong className="text-yellow-400">⚠️ Traps:</strong> MSFT1 and MSST give fake passwords immediately</p>
              <p><strong className="text-yellow-400">🎯 Goal:</strong> Wait for real MSFT to reach {formatPrice(targetPrice)}, then buy MSFT only</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradingHard;