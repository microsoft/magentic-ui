import React, { useState, useEffect } from "react";
import { ChevronLeft, ChevronRight, Clock, CheckCircle } from "lucide-react";
import { RenderMessage } from "./rendermessage";

interface SentinelCheck {
  checkNumber: number;
  messages: any[]; // Agent messages during this check
  reason?: string;
  nextCheckIn?: number;
}

interface RenderSentinelStepProps {
  sentinelId: string;
  title: string;
  condition: string | number;
  sleepDuration: number;
  allMessages: any[]; // All messages from the run
  currentMessageIndex: number; // The index of the sentinel_start message
  sessionId?: number;
  runStatus?: string;
}

const RenderSentinelStep: React.FC<RenderSentinelStepProps> = ({
  sentinelId,
  title,
  condition,
  sleepDuration,
  allMessages,
  currentMessageIndex,
  sessionId = 0,
  runStatus = "",
}) => {
  const [currentCheckIndex, setCurrentCheckIndex] = useState(0);
  const [checks, setChecks] = useState<SentinelCheck[]>([]);
  const [expandedCheck, setExpandedCheck] = useState<number | null>(null);
  const [totalChecks, setTotalChecks] = useState(0);
  const [runtime, setRuntime] = useState(0);
  const [nextCheckIn, setNextCheckIn] = useState<number>(sleepDuration);
  const [currentStatus, setCurrentStatus] = useState<"checking" | "sleeping" | "complete">("checking");
  const [countdown, setCountdown] = useState<number>(0);
  const [lastCheckTime, setLastCheckTime] = useState<number>(Date.now());

  useEffect(() => {
    // Collect all messages related to this sentinel step
    const sentinelMessages = allMessages.filter(
      (msg, idx) =>
        idx > currentMessageIndex &&
        msg.config.metadata?.sentinel_id === sentinelId
    );


    // Group messages by check number
    const checkMap = new Map<number, SentinelCheck>();

    sentinelMessages.forEach((msg) => {
      const metadata = msg.config.metadata;
      const checkNumber = parseInt(metadata?.check_number || "0");

      if (checkNumber > 0) {
        if (!checkMap.has(checkNumber)) {
          checkMap.set(checkNumber, {
            checkNumber,
            messages: [],
          });
        }

        const check = checkMap.get(checkNumber)!;

        // If this is a sentinel_check message, extract check info
        if (metadata?.type === "sentinel_check") {
          check.reason = metadata.reason;
          check.nextCheckIn = parseInt(metadata.next_check_in || "0");
        } else {
          // This is an agent message during the check
          check.messages.push(msg);
        }
      }
    });

    // Find the latest sentinel_check or sentinel_complete message
    const latestStatusMsg = sentinelMessages.reverse().find(msg =>
      msg.config.metadata?.type === "sentinel_check" ||
      msg.config.metadata?.type === "sentinel_complete"
    );
    const latestStatusCheckNumber = parseInt(latestStatusMsg?.config.metadata?.check_number || "0");

    // Determine current status
    if (latestStatusMsg) {
      const metadata = latestStatusMsg.config.metadata;
      setTotalChecks(parseInt(metadata?.total_checks || "0"));
      setRuntime(parseInt(metadata?.runtime || "0"));

      if (metadata?.type === "sentinel_complete") {
        setNextCheckIn(0);
        setCurrentStatus("complete");
        setCountdown(0);
      } else if (metadata?.type === "sentinel_check") {
        const checkInSeconds = parseInt(metadata?.next_check_in || sleepDuration);
        setNextCheckIn(checkInSeconds);

        // Check if there are any agent messages with a check_number higher than the latest sentinel_check
        // This indicates the agent is actively working on the next check
        const activeMessages = sentinelMessages.filter(msg => {
          const msgCheckNumber = parseInt(msg.config.metadata?.check_number || "0");
          const isAgentMessage = msg.config.metadata?.type !== "sentinel_check" &&
                                 msg.config.metadata?.type !== "sentinel_complete" &&
                                 msg.config.metadata?.sentinel_id === sentinelId;
          return isAgentMessage && msgCheckNumber > latestStatusCheckNumber;
        });

        if (activeMessages.length > 0) {
          const activeCheckNumber = parseInt(activeMessages[0].config.metadata?.check_number || "0");

          // Add these active messages to the check map
          if (!checkMap.has(activeCheckNumber)) {
            checkMap.set(activeCheckNumber, {
              checkNumber: activeCheckNumber,
              messages: activeMessages,
              reason: "Actively checking...",
            });
          } else {
            const activeCheck = checkMap.get(activeCheckNumber)!;
            activeCheck.messages = activeMessages;
            activeCheck.reason = "Actively checking...";
          }

          setCurrentStatus("checking");
          setCountdown(0);
        } else {
          // Use the timestamp from the sentinel_check message
          const checkTimestamp = latestStatusMsg.config.timestamp;
          if (checkTimestamp) {
            const checkTime = new Date(checkTimestamp).getTime();
            const elapsed = Math.floor((Date.now() - checkTime) / 1000);
            const remaining = Math.max(0, checkInSeconds - elapsed);
            setCountdown(remaining);
            setLastCheckTime(checkTime);
          } else {
            setCountdown(checkInSeconds);
            setLastCheckTime(Date.now());
          }
          setCurrentStatus("sleeping");
        }
      }
    } else {
      // If no status messages yet, we're still checking (check #1)
      const check1Messages = sentinelMessages.filter(msg => {
        const msgCheckNumber = parseInt(msg.config.metadata?.check_number || "0");
        return msgCheckNumber === 1 &&
               msg.config.metadata?.type !== "sentinel_check" &&
               msg.config.metadata?.type !== "sentinel_complete";
      });

      if (!checkMap.has(1)) {
        checkMap.set(1, {
          checkNumber: 1,
          messages: check1Messages,
          reason: "Actively checking...",
        });
      }

      setCurrentStatus("checking");
    }

    // Convert map to sorted array and set current check to the latest
    const checkArray = Array.from(checkMap.values()).sort((a, b) => a.checkNumber - b.checkNumber);
    setChecks(checkArray);
    if (checkArray.length > 0) {
      setCurrentCheckIndex(checkArray.length - 1);
    }
  }, [allMessages, currentMessageIndex, sentinelId, sleepDuration]);

  // Countdown timer effect
  useEffect(() => {
    if (currentStatus !== "sleeping" || countdown <= 0) {
      return;
    }

    const interval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - lastCheckTime) / 1000);
      const remaining = Math.max(0, nextCheckIn - elapsed);
      setCountdown(remaining);

      if (remaining === 0) {
        clearInterval(interval);
        // Auto-switch to checking when timeout reaches 0
        setCurrentStatus("checking");
      }
    }, 100); // Update every 100ms for smooth countdown

    return () => clearInterval(interval);
  }, [currentStatus, countdown, nextCheckIn, lastCheckTime]);

  const currentCheck = checks[currentCheckIndex];

  const formatTime = (seconds: number): string => {
    const plural = (n: number, unit: string) => `${n} ${unit}${n !== 1 ? 's' : ''}`;

    if (seconds < 60) {
      return plural(seconds, 'second');
    }

    if (seconds < 3600) {
      const minutes = Math.floor(seconds / 60);
      const secs = seconds % 60;
      return secs === 0 ? plural(minutes, 'minute') : `${plural(minutes, 'minute')} ${plural(secs, 'second')}`;
    }

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    let result = plural(hours, 'hour');
    if (minutes > 0) result += ` ${plural(minutes, 'minute')}`;
    if (secs > 0) result += ` ${plural(secs, 'second')}`;
    return result;
  };

  const getStatusIcon = () => {
    switch (currentStatus) {
      case "complete":
        return <CheckCircle size={20} className="text-green-600" />;
      case "sleeping":
        return <Clock size={20} className="text-blue-600" />;
      default:
        return null;
    }
  };

  const getStatusText = () => {
    switch (currentStatus) {
      case "complete":
        if (typeof condition === 'number') {
          return `Completed ${condition} iteration${condition !== 1 ? 's' : ''}`;
        }
        return `Completed after ${totalChecks} check${totalChecks !== 1 ? 's' : ''}`;
      case "checking":
        if (typeof condition === 'number') {
          return `Checking (${totalChecks}/${condition})...`;
        }
        return "Checking condition...";
      default:
        return `Sleeping... next check in ${countdown}s`;
    }
  };

  return (
    <div className="space-y-2">
      {/* Main sentinel step box */}
      <div className="border-2 border-secondary rounded-lg p-4 bg-secondary">
        <div className="flex items-center justify-between mb-2">
          <div className="font-semibold text-primary">{title}</div>
          <div className="flex items-center gap-2">
            {getStatusIcon()}
            <span className="text-sm">{getStatusText()}</span>
          </div>
        </div>
        <div className="text-sm space-y-1">
          <div>
            <span className="">Total checks: </span>
            <span className="text-primary">{totalChecks}</span>
          </div>
          <div>
            <span className="">Runtime so far: </span>
            <span className="text-primary">{formatTime(runtime)}</span>
          </div>
        </div>
      </div>

      {/* Check history box */}
      {checks.length > 0 && (
        <div className="border-2 border-secondary rounded-lg p-4 bg-tertiary">
          <div className="flex items-center justify-between mb-3">
            <div className="font-semibold text-primary">Check History</div>
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  setCurrentCheckIndex(Math.max(0, currentCheckIndex - 1))
                }
                disabled={currentCheckIndex === 0}
                className="p-1 rounded hover:bg-secondary disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label="Previous check"
              >
                <ChevronLeft size={20} />
              </button>
              <span className="text-sm">
                Check {currentCheck?.checkNumber || 0} of {checks.length}
              </span>
              <button
                onClick={() =>
                  setCurrentCheckIndex(
                    Math.min(checks.length - 1, currentCheckIndex + 1)
                  )
                }
                disabled={currentCheckIndex === checks.length - 1}
                className="p-1 rounded hover:bg-secondary disabled:opacity-30 disabled:cursor-not-allowed"
                aria-label="Next check"
              >
                <ChevronRight size={20} />
              </button>
            </div>
          </div>

          {/* Current check details */}
          {currentCheck && (
            <div className="space-y-2">
              <div className="text-sm">
                {currentCheck.reason ||
                  `Check #${currentCheck.checkNumber} - Condition not yet satisfied`}
              </div>

              {/* Expandable section for agent messages */}
              {currentCheck.messages.length > 0 && (
                <div className="mt-2">
                  <button
                    onClick={() => setExpandedCheck(
                      expandedCheck === currentCheck.checkNumber ? null : currentCheck.checkNumber
                    )}
                    className="text-sm text-magenta-800 hover:text-magenta-900 underline"
                  >
                    {expandedCheck === currentCheck.checkNumber ? "Hide" : "Show"} check steps ({currentCheck.messages.length})
                  </button>

                  {expandedCheck === currentCheck.checkNumber && (
                    <div className="mt-2 space-y-1">
                      {currentCheck.messages.map((msg, idx) => (
                        <RenderMessage
                          key={idx}
                          message={msg.config}
                          sessionId={sessionId}
                          messageIdx={allMessages.findIndex(m => m === msg)}
                          runStatus={runStatus}
                          allMessages={allMessages}
                          skipSentinelHiding={true}
                        />
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default RenderSentinelStep;
