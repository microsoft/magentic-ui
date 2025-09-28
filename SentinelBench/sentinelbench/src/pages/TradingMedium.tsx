import { useState, useEffect } from "react";
import { useTaskAnalytics } from "../utils/useTaskAnalytics";
import { TaskStateManager } from "../utils/TaskStateManager";
import { generateParameterPassword } from "../utils/parameterPassword";
import { URLParameterHandler } from "../utils/urlParameterHandler";
import { DURATION } from "../config/constants";

export const TASK_ID_TradingMedium = "trading-medium";

interface Stock {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePercent: number;
  color: string;
  logo: string;
}

const TradingMedium = () => {
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
    const savedState = TaskStateManager.loadState(TASK_ID_TradingMedium);
    
    // Check if we should reset state based on parameter changes
    if (URLParameterHandler.shouldResetState(TASK_ID_TradingMedium, savedState, params)) {
      TaskStateManager.clearState(TASK_ID_TradingMedium);
      
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        hasPlacedOrder: false,
        staticPassword: generateParameterPassword(TASK_ID_TradingMedium, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_TradingMedium, initialState);
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
        staticPassword: generateParameterPassword(TASK_ID_TradingMedium, savedDuration)
      };
    } else {
      // Fresh start - use default duration
      const now = Date.now();
      const initialState = {
        startTime: now,
        duration: taskDuration,
        showPassword: false,
        hasPlacedOrder: false,
        staticPassword: generateParameterPassword(TASK_ID_TradingMedium, taskDuration)
      };
      
      TaskStateManager.saveState(TASK_ID_TradingMedium, initialState);
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
  const [staticPassword, setStaticPassword] = useState(initialState.staticPassword || "");
  const [currentTime, setCurrentTime] = useState(Date.now());
  const [orderMessage, setOrderMessage] = useState("");
  const [selectedStock, setSelectedStock] = useState("MSFT");

  // Initialize stock data
  const [stocks, setStocks] = useState<Stock[]>([
    { symbol: "MSFT", name: "Microsoft Corporation", price: 500.00, change: 0, changePercent: 0, color: "blue", logo: "M" },
    { symbol: "AAPL", name: "Apple Inc.", price: 180.50, change: 0, changePercent: 0, color: "gray", logo: "🍎" },
    { symbol: "GOOGL", name: "Alphabet Inc.", price: 142.30, change: 0, changePercent: 0, color: "red", logo: "G" },
    { symbol: "AMZN", name: "Amazon.com Inc.", price: 155.80, change: 0, changePercent: 0, color: "orange", logo: "A" },
    { symbol: "TSLA", name: "Tesla, Inc.", price: 248.20, change: 0, changePercent: 0, color: "green", logo: "T" },
    { symbol: "NVDA", name: "NVIDIA Corporation", price: 875.60, change: 0, changePercent: 0, color: "green", logo: "N" }
  ]);

  const { recordSuccess } = useTaskAnalytics(TASK_ID_TradingMedium);
  
  // Record success if resuming to an already completed state
  useEffect(() => {
    if (initialState.showPassword) {
      recordSuccess();
    }
  }, [initialState.showPassword, recordSuccess]);

  // Save state whenever any state variable changes
  useEffect(() => {
    const currentState = {
      startTime,
      duration: tradingDuration,
      showPassword,
      hasPlacedOrder,
      staticPassword
    };
    
    TaskStateManager.saveState(TASK_ID_TradingMedium, currentState);
  }, [startTime, tradingDuration, showPassword, hasPlacedOrder, staticPassword]);

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
        } else {
          // Other stocks fluctuate randomly
          const originalPrice = stock.symbol === 'AAPL' ? 180.50 :
                               stock.symbol === 'GOOGL' ? 142.30 :
                               stock.symbol === 'AMZN' ? 155.80 :
                               stock.symbol === 'TSLA' ? 248.20 : 875.60;
          
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
  const canPlaceOrder = progress >= 1 && selectedStock === 'MSFT' && selectedStockData && selectedStockData.price <= targetPrice && !hasPlacedOrder;

  const handleBuyOrder = () => {
    if (!canPlaceOrder) {
      setOrderMessage("Order cannot be placed at this time.");
      setTimeout(() => setOrderMessage(""), 3000);
      return;
    }

    // Success! Place order and show password
    const finalPassword = generateParameterPassword(TASK_ID_TradingMedium, tradingDuration);
    setStaticPassword(finalPassword);
    setShowPassword(true);
    setHasPlacedOrder(true);
    setOrderMessage("Order placed successfully!");
    recordSuccess();
  };

  const formatPrice = (price: number) => `$${price.toFixed(2)}`;

  return (
    <div className="min-h-screen bg-black">
      {/* Raulhood Header */}
      <header className="bg-black border-b border-gray-800">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-8">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 bg-green-500 rounded-full flex items-center justify-center">
                  <span className="text-black font-bold text-sm">R</span>
                </div>
                <span className="text-white font-bold text-lg">Raulhood</span>
              </div>
              <nav className="hidden md:flex items-center space-x-6 text-sm">
                <a href="#" className="text-white hover:text-green-400 transition-colors">Investing</a>
                <a href="#" className="text-gray-400 hover:text-green-400 transition-colors">Crypto</a>
                <a href="#" className="text-gray-400 hover:text-green-400 transition-colors">Retirement</a>
                <a href="#" className="text-gray-400 hover:text-green-400 transition-colors">Learn</a>
              </nav>
            </div>
            <div className="flex items-center space-x-4">
              <button className="text-gray-400 hover:text-white transition-colors">🔍</button>
              <button className="text-gray-400 hover:text-white transition-colors">👤</button>
            </div>
          </div>
        </div>
      </header>

      {/* Development Tools */}
      {(isLocalhost || adminConsoleEnabled) && (
        <div className="bg-gradient-to-r from-yellow-50 to-amber-50 border border-yellow-200/50 mx-4 mt-4 rounded-xl p-4 shadow-sm backdrop-blur-sm">
          <div className="flex items-center justify-between text-sm">
            <div className="text-yellow-800 font-medium">
              <strong>Dev Tools:</strong> Duration: {tradingDuration}s | 
              Elapsed: {elapsedTime}s | 
              MSFT: {formatPrice(selectedStockData?.price || 0)} | 
              Target: {formatPrice(targetPrice)} | 
              Progress: {(progress * 100).toFixed(1)}% |
              Persistent: {TaskStateManager.hasState(TASK_ID_TradingMedium) ? '✅' : '❌'}
            </div>
            <button 
              onClick={() => {
                if (window.confirm('Are you sure you want to reset this task? This will restart the trading simulation from the beginning.')) {
                  TaskStateManager.clearState(TASK_ID_TradingMedium);
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
        {/* Main Content */}
        <div className="flex">
          {/* Left Sidebar - Watchlist */}
          <div className="w-80 px-4 py-6">
            {/* Account Summary */}
            <div className="bg-gray-900 rounded-lg p-4 mb-6">
              <div className="text-center">
                <div className="text-xl font-bold text-white">$10,000.00</div>
                <div className="text-gray-400 text-sm">Buying Power</div>
              </div>
              <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-gray-700">
                <div className="text-center">
                  <div className="text-green-400 font-medium">+$234.50</div>
                  <div className="text-gray-400 text-xs">Today</div>
                </div>
                <div className="text-center">
                  <div className="text-white font-medium">$25,432.50</div>
                  <div className="text-gray-400 text-xs">Portfolio</div>
                </div>
              </div>
            </div>

            {/* Stock List */}
            <div className="bg-gray-900 rounded-lg">
              <div className="p-4 border-b border-gray-700">
                <h2 className="text-white font-bold">Markets</h2>
              </div>
              <div className="divide-y divide-gray-700">
                {stocks.map((stock) => (
                  <div
                    key={stock.symbol}
                    onClick={() => setSelectedStock(stock.symbol)}
                    className={`p-4 cursor-pointer hover:bg-gray-800 transition-colors ${
                      selectedStock === stock.symbol ? 'bg-gray-800 border-l-4 border-green-500' : ''
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className={`w-8 h-8 bg-${stock.color}-600 rounded-lg flex items-center justify-center`}>
                          <span className="text-white font-bold text-xs">{stock.logo}</span>
                        </div>
                        <div>
                          <div className="text-white font-medium text-sm">{stock.symbol}</div>
                          <div className="text-gray-400 text-xs">{stock.name.length > 15 ? stock.name.substring(0, 15) + '...' : stock.name}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-white font-medium text-sm">{formatPrice(stock.price)}</div>
                        <div className={`text-xs ${stock.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Main Feed */}
          <div className="flex-1 px-4 py-6">
            {/* Selected Stock Details */}
            {selectedStockData && (
              <div className="bg-gray-900 rounded-lg p-6 mb-6">
                <div className="flex items-start justify-between mb-6">
                  <div className="flex items-center space-x-4">
                    <div className={`w-16 h-16 bg-gradient-to-br from-${selectedStockData.color}-500 to-${selectedStockData.color}-600 rounded-xl flex items-center justify-center`}>
                      <span className="text-white font-bold text-2xl">{selectedStockData.logo}</span>
                    </div>
                    <div>
                      <h2 className="text-white text-2xl font-bold">{selectedStockData.name}</h2>
                      <p className="text-gray-400 text-lg">{selectedStockData.symbol} • NASDAQ</p>
                      <div className="flex items-center space-x-2 mt-1">
                        <span className="text-xs text-gray-500 bg-gray-800 px-2 py-1 rounded">Real-time</span>
                        <span className="text-xs text-gray-500">•</span>
                        <span className="text-xs text-gray-500">USD</span>
                      </div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-white text-4xl font-bold">{formatPrice(selectedStockData.price)}</div>
                    <div className={`text-lg font-medium flex items-center justify-end space-x-1 mt-1 ${
                      selectedStockData.change >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      <span>{selectedStockData.change >= 0 ? '▲' : '▼'}</span>
                      <span>{formatPrice(Math.abs(selectedStockData.change))} ({Math.abs(selectedStockData.changePercent).toFixed(2)}%)</span>
                    </div>
                    <div className="text-gray-400 text-sm mt-1">Today</div>
                  </div>
                </div>

                {/* Stock Stats */}
                <div className="grid grid-cols-2 gap-6 mb-6 p-4 bg-gray-800 rounded-lg">
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">Market Cap</span>
                      <span className="text-white font-medium">
                        {selectedStock === 'MSFT' ? '$3.78T' : 
                         selectedStock === 'AAPL' ? '$2.89T' :
                         selectedStock === 'GOOGL' ? '$1.89T' :
                         selectedStock === 'AMZN' ? '$1.56T' :
                         selectedStock === 'TSLA' ? '$789B' : '$2.1T'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">P/E Ratio</span>
                      <span className="text-white font-medium">
                        {selectedStock === 'MSFT' ? '34.12' : 
                         selectedStock === 'AAPL' ? '28.4' :
                         selectedStock === 'GOOGL' ? '22.8' :
                         selectedStock === 'AMZN' ? '52.1' :
                         selectedStock === 'TSLA' ? '68.9' : '45.3'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Volume</span>
                      <span className="text-white font-medium">
                        {selectedStock === 'MSFT' ? '23.4M' : 
                         selectedStock === 'AAPL' ? '45.2M' :
                         selectedStock === 'GOOGL' ? '18.7M' :
                         selectedStock === 'AMZN' ? '32.1M' :
                         selectedStock === 'TSLA' ? '78.9M' : '19.5M'}
                      </span>
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-400">52W High</span>
                      <span className="text-white font-medium">
                        {selectedStock === 'MSFT' ? '$468.35' : 
                         selectedStock === 'AAPL' ? '$199.62' :
                         selectedStock === 'GOOGL' ? '$191.18' :
                         selectedStock === 'AMZN' ? '$201.20' :
                         selectedStock === 'TSLA' ? '$299.29' : '$1,037.99'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">52W Low</span>
                      <span className="text-white font-medium">
                        {selectedStock === 'MSFT' ? '$309.45' : 
                         selectedStock === 'AAPL' ? '$164.08' :
                         selectedStock === 'GOOGL' ? '$121.46' :
                         selectedStock === 'AMZN' ? '$118.35' :
                         selectedStock === 'TSLA' ? '$152.37' : '$475.27'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-400">Dividend</span>
                      <span className="text-white font-medium">
                        {selectedStock === 'MSFT' ? '0.68%' : 
                         selectedStock === 'AAPL' ? '0.44%' :
                         selectedStock === 'GOOGL' ? '—' :
                         selectedStock === 'AMZN' ? '—' :
                         selectedStock === 'TSLA' ? '—' : '0.15%'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Order Interface */}
                <div className="space-y-4">
                  <div className="flex space-x-4">
                    <button
                      onClick={handleBuyOrder}
                      disabled={hasPlacedOrder}
                      className={`flex-1 py-4 px-6 rounded-lg font-bold text-lg transition-all ${
                        hasPlacedOrder
                          ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                          : canPlaceOrder
                          ? 'bg-green-500 hover:bg-green-600 text-black shadow-lg hover:shadow-green-500/25'
                          : 'bg-green-600 text-black cursor-not-allowed opacity-50'
                      }`}
                    >
                      {hasPlacedOrder ? '✓ Order Placed' : `Buy $${selectedStock}`}
                    </button>
                    <button
                      disabled={true}
                      className="flex-1 py-4 px-6 rounded-lg font-bold text-lg bg-gray-700 text-gray-500 cursor-not-allowed"
                    >
                      Sell ${selectedStock}
                    </button>
                  </div>

                  {orderMessage && (
                    <div className={`text-center p-4 rounded-lg ${
                      orderMessage.includes('successfully') 
                        ? 'bg-green-900/30 border border-green-500/30 text-green-400' 
                        : 'bg-yellow-900/30 border border-yellow-500/30 text-yellow-400'
                    }`}>
                      {orderMessage}
                    </div>
                  )}

                  {/* Order Details */}
                  <div className="bg-gray-800 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-gray-400">Order Type</span>
                      <span className="text-white">Market Order</span>
                    </div>
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-gray-400">Quantity</span>
                      <span className="text-white">1 Share</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-gray-400">Est. Total</span>
                      <span className="text-white font-medium">{formatPrice(selectedStockData.price)}</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Right Sidebar */}
          <div className="w-80 px-4 py-6">
            {/* News */}
            <div className="bg-gray-900 rounded-lg p-4 mb-6">
              <h3 className="text-white font-bold mb-4">News</h3>
              <div className="space-y-4">
                <div className="flex space-x-3">
                  <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
                    <span className="text-white text-xs font-bold">R</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-white text-sm font-medium leading-tight">Microsoft announces new AI initiatives for cloud computing</p>
                    <p className="text-gray-400 text-xs mt-1">Reuters • 2h ago</p>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
                    <span className="text-white text-xs font-bold">B</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-white text-sm font-medium leading-tight">Tech stocks show mixed performance amid market volatility</p>
                    <p className="text-gray-400 text-xs mt-1">Bloomberg • 4h ago</p>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <div className="w-10 h-10 bg-gray-700 rounded-lg flex items-center justify-center">
                    <span className="text-white text-xs font-bold">C</span>
                  </div>
                  <div className="flex-1">
                    <p className="text-white text-sm font-medium leading-tight">Tesla reports strong Q4 delivery numbers</p>
                    <p className="text-gray-400 text-xs mt-1">CNBC • 6h ago</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Popular Lists */}
            <div className="bg-gray-900 rounded-lg p-4">
              <h3 className="text-white font-bold mb-4">100 Most Popular</h3>
              <div className="space-y-3">
                {stocks.slice(0, 4).map((stock, index) => (
                  <div key={stock.symbol} className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <span className="text-gray-400 text-sm">{index + 1}</span>
                      <div>
                        <div className="text-white font-medium">{stock.symbol}</div>
                        <div className="text-gray-400 text-xs">{stock.name.length > 12 ? stock.name.substring(0, 12) + '...' : stock.name}</div>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-white">{formatPrice(stock.price)}</div>
                      <div className={`text-xs ${stock.change >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Success Message */}
        {showPassword && (
          <div className="px-4 pb-6">
            <div className="bg-green-900/30 border border-green-500/30 rounded-lg p-6 text-center">
              <h2 
                id="trading-status"
                data-state="completed"
                className="text-xl font-bold text-green-400 mb-2"
              >
                🎉 Trade Completed Successfully!
              </h2>
              <p className="text-green-300 mb-4">
                Your order has been executed successfully!
              </p>
              <div className="bg-green-900/50 p-3 rounded-lg">
                <p className="text-green-300 font-medium mb-1">Access Code:</p>
                <code 
                  id="access-code"
                  className="font-mono font-bold text-lg text-green-400"
                >
                  {staticPassword || generateParameterPassword(TASK_ID_TradingMedium, tradingDuration)}
                </code>
              </div>
            </div>
          </div>
        )}

        {/* Technical Hints */}
        {showHints && (
          <div className="px-4 pb-6">
            <div className="bg-gray-900 text-green-400 rounded-lg p-6 border-2 border-green-500 font-mono">
              <h3 className="font-bold text-green-300 mb-3 text-lg">🛠️ TECHNICAL SPECIFICATIONS</h3>
              <div className="text-sm space-y-2">
                <p><strong className="text-yellow-400">🎯 Status Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#trading-status</code></p>
                <p><strong className="text-yellow-400">✅ Completion State:</strong> <code className="bg-gray-700 px-2 py-1 rounded">data-state="completed"</code></p>
                <p><strong className="text-yellow-400">🔓 Code Element:</strong> <code className="bg-gray-700 px-2 py-1 rounded">#access-code</code></p>
                <p><strong className="text-yellow-400">⏱️ Duration:</strong> {Math.floor(tradingDuration / 60)}:{(tradingDuration % 60).toString().padStart(2, '0')} minutes</p>
                <p><strong className="text-yellow-400">💰 Target Price:</strong> {formatPrice(targetPrice)} (90% of {formatPrice(500)})</p>
                <p><strong className="text-yellow-400">📈 Stocks:</strong> 6 stocks total, only MSFT achieves target</p>
                <p><strong className="text-yellow-400">🎯 Goal:</strong> Wait for MSFT to reach {formatPrice(targetPrice)}, then buy MSFT</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default TradingMedium;