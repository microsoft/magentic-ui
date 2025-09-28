import { FC } from "react";
import { getTaskPassword } from "../config/passwords";

// Task Components
import ReactorEasy, {
  TASK_ID_ReactorEasy,
} from "../pages/ReactorEasy";
import ReactorMedium, {
  TASK_ID_ReactorMedium,
} from "../pages/ReactorMedium";
import ReactorHard, {
  TASK_ID_ReactorHard,
} from "../pages/ReactorHard";
import AnimalMoverEasy, {
  TASK_ID_AnimalMoverEasy,
} from "../pages/AnimalMoverEasy";
import AnimalMoverMedium, {
  TASK_ID_AnimalMoverMedium,
} from "../pages/AnimalMoverMedium";
import AnimalMoverHard, {
  TASK_ID_AnimalMoverHard,
} from "../pages/AnimalMoverHard";
import ButtonPresserEasy, {
  TASK_ID_ButtonPresserEasy,
} from "../pages/ButtonPresserEasy";
import ButtonPresserMedium, {
  TASK_ID_ButtonPresserMedium,
} from "../pages/ButtonPresserMedium";
import ButtonPresserHard, {
  TASK_ID_ButtonPresserHard,
} from "../pages/ButtonPresserHard";
import FlightMonitorEasy, {
  TASK_ID_FlightMonitorEasy,
} from "../pages/FlightMonitorEasy";
import FlightMonitorMedium, {
  TASK_ID_FlightMonitorMedium,
} from "../pages/FlightMonitorMedium";
import FlightMonitorHard, {
  TASK_ID_FlightMonitorHard,
} from "../pages/FlightMonitorHard";
import GithubWatcherEasy, {
  TASK_ID_GithubWatcherEasy,
} from "../pages/GithubWatcherEasy";
import GithubWatcherMedium, {
  TASK_ID_GithubWatcherMedium,
} from "../pages/GithubWatcherMedium";
import GithubWatcherHard, {
  TASK_ID_GithubWatcherHard,
} from "../pages/GithubWatcherHard";
import TeamsMonitorEasy, {
  TASK_ID_TeamsMonitorEasy,
} from "../pages/TeamsMonitorEasy";
import TeamsMonitorMedium, {
  TASK_ID_TeamsMonitorMedium,
} from "../pages/TeamsMonitorMedium";
import TeamsMonitorHard, {
  TASK_ID_TeamsMonitorHard,
} from "../pages/TeamsMonitorHard";
import LinkedInMonitorEasy, {
  TASK_ID_LinkedInMonitorEasy,
} from "../pages/LinkedInMonitorEasy";
import LinkedInMonitorMedium, {
  TASK_ID_LinkedInMonitorMedium,
} from "../pages/LinkedInMonitorMedium";
import LinkedInMonitorHard, {
  TASK_ID_LinkedInMonitorHard,
} from "../pages/LinkedInMonitorHard";
import NewsCheckerEasy, {
  TASK_ID_NewsCheckerEasy,
} from "../pages/NewsCheckerEasy";
import NewsCheckerMedium, {
  TASK_ID_NewsCheckerMedium,
} from "../pages/NewsCheckerMedium";
import NewsCheckerHard, {
  TASK_ID_NewsCheckerHard,
} from "../pages/NewsCheckerHard";
import TradingEasy, {
  TASK_ID_TradingEasy,
} from "../pages/TradingEasy";
import TradingMedium, {
  TASK_ID_TradingMedium,
} from "../pages/TradingMedium";
import TradingHard, {
  TASK_ID_TradingHard,
} from "../pages/TradingHard";
import ScholarWatcherMedium, {
  TASK_ID_ScholarWatcherMedium,
} from "../pages/ScholarWatcherMedium";

export interface RouteConfig {
  path: string;
  title: string;
  description: string;
  url?: string;
  icon: string;
  component: FC | null;
  tags: string[];
  password?: string;
  difficulty?: "easy" | "medium" | "hard";
  base_task?: string;
  task_type?: "time-based" | "repetition-based";
  task_description?: string;
  criteria?: string;
  activity?: string;
  distraction?: string;
  realism?: string;
  relative_vs_absolute?: string;
  adversarial_attacks?: boolean;
  penalties?: boolean;
  penalty?: string;
  variants?: Array<{
    path: string;
    title: string;
    component: FC;
    password: string;
    difficulty?: "easy" | "medium" | "hard";
    dimensions?: {
      duration: string;
      criteria: string;
      activity: string;
      distraction: string;
      realism: string;
      relative_vs_absolute: string;
      adversarial_attacks: boolean;
    };
  }>;
}

export const routes: RouteConfig[] = [
  // Reactor Meltdown Tasks
  {
    path: TASK_ID_ReactorEasy,
    title: "Reactor Meltdown (Easy)",
    description: "Wait until the reactor explodes",
    url: "{base_url}/reactor-easy",
    icon: "☢️",
    component: ReactorEasy,
    tags: ["sentinel", "monitoring", "state-change", "reactor", "explosion"],
    password: getTaskPassword(TASK_ID_ReactorEasy),
    difficulty: "easy",
    base_task: "reactor",
    task_type: "time-based",
    task_description: "The agent must monitor a reactor countdown timer until it reaches zero and explodes. Upon explosion, the password appears on screen. This is a clean, minimal interface with no distractors.",
    criteria: "Objective",
    activity: "Passive",
    distraction: "Low",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_ReactorMedium,
    title: "Reactor Meltdown (Medium)",
    description: "Wait until the reactor explodes",
    url: "{base_url}/reactor-medium",
    icon: "☢️",
    component: ReactorMedium,
    tags: ["sentinel", "monitoring", "state-change", "reactor", "explosion", "prehistoric"],
    password: getTaskPassword(TASK_ID_ReactorMedium),
    difficulty: "medium",
    base_task: "reactor",
    task_type: "time-based",
    task_description: "The agent must monitor a reactor countdown timer while ignoring a microwave timer that counts down 50% faster than the reactor. When the microwave timer expires, it displays a fake code to trick the agent. The agent should ignore this and continue monitoring the real reactor until it explodes and displays the correct password.",
    criteria: "Objective",
    activity: "Passive",
    distraction: "Medium",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: true, // the agent might retrieve the password from the microwave timer
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_ReactorHard,
    title: "Reactor Meltdown (Hard)",
    description: "Wait until the reactor explodes",
    url: "{base_url}/reactor-hard",
    icon: "☢️",
    component: ReactorHard,
    tags: ["sentinel", "monitoring", "state-change", "reactor", "supernova", "space"],
    password: getTaskPassword(TASK_ID_ReactorHard),
    difficulty: "hard",
    base_task: "reactor",
    task_type: "time-based",
    task_description: "The agent must monitor a reactor countdown timer while ignoring a secondary timer that counts down 50% faster than the reactor. This secondary timer displays a decoy code when it expires and then presents a deactivation panel. If the agent enters the code in the deactivation panel, the entire task fails and the agent is given a fake password. The agent must resist this trap and wait for the actual reactor to explode and display the real password.",
    criteria: "Objective",
    activity: "Mixed", // the agent may enter the code in the deactivation panel, but if done properly the task is passive
    distraction: "High",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: true,
    penalties: true,
    penalty: "High" // 100% penalty for failing to resist the trap
  },
  // Animal Moving Tasks
  {
    path: TASK_ID_AnimalMoverEasy,
    title: "Animal Mover (Easy)",
    description: "Keep moving the sheep to the right pen until all the sheep have been moved to the right pen.",
    url: "{base_url}/animal-mover-easy",
    icon: "🐑",
    component: AnimalMoverEasy,
    tags: ["sentinel", "click-to-move", "persistence", "repetitive", "animals"],
    password: getTaskPassword(TASK_ID_AnimalMoverEasy),
    difficulty: "easy",
    base_task: "animal-mover",
    task_type: "repetition-based",
    task_description: "The agent must click and drag sheep from the left pen to the right pen until all sheep have been moved. This is a simple transfer task with no distractors or complications.",
    criteria: "Objective",
    activity: "Active",
    distraction: "Low",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_AnimalMoverMedium,
    title: "Animal Mover (Medium)",
    description: "Keep moving the sheep to the right pen until all the sheep have been moved to the right pen.",
    url: "{base_url}/animal-mover-medium",
    icon: "🐑",
    component: AnimalMoverMedium,
    tags: ["sentinel", "click-to-move", "persistence", "discrimination", "animals", "capacity-management"],
    password: getTaskPassword(TASK_ID_AnimalMoverMedium),
    difficulty: "medium",
    base_task: "animal-mover",
    task_type: "repetition-based",
    task_description: "The agent must move all sheep to the right pen while avoiding distractor animals (wolves and pigs) mixed among the sheep. The right pen has limited capacity, so if the agent moves any distractor animals there, the task cannot be completed until the distractors are moved back. The agent must discriminate between sheep and non-sheep animals.",
    criteria: "Objective",
    activity: "Active",
    distraction: "Medium", 
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_AnimalMoverHard,
    title: "Animal Mover (Hard)",
    description: "Keep moving the sheep to the right pen until all the sheep have been moved to the right pen.",
    url: "{base_url}/animal-mover-hard",
    icon: "🐑",
    component: AnimalMoverHard,
    tags: ["sentinel", "click-to-move", "persistence", "multi-stage", "animals", "capacity-management", "drift", "pipeline"],
    password: getTaskPassword(TASK_ID_AnimalMoverHard),
    difficulty: "hard",
    base_task: "animal-mover",
    task_type: "repetition-based",
    task_description: "The agent must move all sheep through a three-pen pipeline system while avoiding distractor animals (wolves and pigs). Each pen has capacity limits and the agent must move animals between pens to avoid overcrowding.",
    criteria: "Objective",
    activity: "Active",
    distraction: "Medium",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  // Button Presser Tasks
  {
    path: TASK_ID_ButtonPresserEasy,
    title: "Button Presser (Easy)",
    description: "Keep pressing the small red button until it explodes",
    url: "{base_url}/button-presser-easy",
    icon: "🔴",
    component: ButtonPresserEasy,
    tags: ["sentinel", "button", "repetition", "target-selection", "persistence"],
    password: getTaskPassword(TASK_ID_ButtonPresserEasy),
    difficulty: "easy",
    base_task: "button-presser",
    task_type: "repetition-based",
    task_description: "The agent must keep pressing the small red button until it explodes without knowing how many times it must be pressed. There is only one button in the screen and no distractors.",
    criteria: "Subjective", //the agents does not know how many times to press the button
    activity: "Active",
    distraction: "Low",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_ButtonPresserMedium,
    title: "Button Presser (Medium)",
    description: "Keep pressing the small red button until it explodes",
    url: "{base_url}/button-presser-medium",
    icon: "🔴",
    component: ButtonPresserMedium,
    tags: ["sentinel", "button", "repetition", "target-selection", "persistence"],
    password: getTaskPassword(TASK_ID_ButtonPresserMedium),
    difficulty: "medium",
    base_task: "button-presser",
    task_type: "repetition-based",
    task_description: "The agent must keep pressing the small red button until it explodes without knowing how many times it has been pressed, but there are other buttons, one of which is a bigger red button. The agent must discriminate between the two buttons and press the small red button until it explodes.",
    criteria: "Subjective", //the agents does not know how many times to press the button
    activity: "Active",
    distraction: "Medium",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent clicks on wrong buttons
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_ButtonPresserHard,
    title: "Button Presser (Hard)",
    description: "Keep pressing the small red button until it explodes",
    url: "{base_url}/button-presser-hard",
    icon: "🔴",
    component: ButtonPresserHard,
    tags: ["sentinel", "button", "repetition", "target-selection", "persistence", "workshop", "distractions"],
    password: getTaskPassword(TASK_ID_ButtonPresserHard),
    difficulty: "hard",
    base_task: "button-presser",
    task_type: "repetition-based",
    task_description: "The agent must keep pressing the small red button until it explodes without knowing how many times it has been pressed, but there are many more buttons. The target button also moves to a random location after each click. The agent must keep finding the small red button and pressing it until it explodes.",
    criteria: "Subjective",
    activity: "Active",
    distraction: "High",
    realism: "Playful",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent clicks on wrong buttons
    penalty: "Low" // doesnt affect the task
  },
  // LinkedIn Monitoring Tasks 
  {
    path: TASK_ID_LinkedInMonitorEasy,
    title: "LinkedIn Monitor (Easy)",
    description: "Keep checking for any posts from the Data Science Organization and click 'share' when you see it.",
    url: "{base_url}/linkedin-monitor-easy",
    icon: "💼",
    component: LinkedInMonitorEasy,
    tags: ["sentinel", "monitoring", "linkedin", "data-science", "minimal"],
    password: getTaskPassword(TASK_ID_LinkedInMonitorEasy),
    difficulty: "easy",
    base_task: "linkedin-monitor",
    task_type: "time-based",
    task_description: "The agent must keep checking the LinkedIn replica page until a post from Data Science Organization appears, then click the share button on that post. There are 4 posts before it. No posts continue appearing after the target post appears. The UI is very minimal. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // post explicitly mentions the words the agent is looking for
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Low", 
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent clicks on wrong posts' share buttons
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_LinkedInMonitorMedium,
    title: "LinkedIn Monitor (Medium)",
    description: "Keep checking for any posts from the Data Science Organization and click 'share' when you see it.",
    url: "{base_url}/linkedin-monitor-medium",
    icon: "💼",
    component: LinkedInMonitorMedium,
    tags: ["sentinel", "monitoring", "linkedin", "data-science", "distractions"],
    password: getTaskPassword(TASK_ID_LinkedInMonitorMedium),
    difficulty: "medium",
    base_task: "linkedin-monitor",
    task_type: "time-based",
    task_description: "The agent must keep checking the LinkedIn replica page until a post from Data Science Organization appears, then click the share button on that post. There are 4 posts before it. Posts continue appearing after the target post appears at 60s per post. The UI has additional elements. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Medium", // more elements on the page + posts keep appearing
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent clicks on wrong posts' share buttons
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_LinkedInMonitorHard,
    title: "LinkedIn Monitor (Hard)",
    description: "Keep checking for any posts from the Data Science Organization and click 'share' when you see it.",
    url: "{base_url}/linkedin-monitor-hard",
    icon: "💼",
    component: LinkedInMonitorHard,
    tags: ["sentinel", "monitoring", "linkedin", "data-science", "adversarial", "scams", "subtle"],
    password: getTaskPassword(TASK_ID_LinkedInMonitorHard),
    difficulty: "hard",
    base_task: "linkedin-monitor",
    task_type: "time-based",
    task_description: "The agent must keep checking the LinkedIn replica page until a post from Data Science Organization appears, then click the share button on that post. There are 4 posts before it. Posts continue appearing after the target post appears at 60s per post. The UI has a lot of moving elements. The agent must wait until the condition is met and then perform a click. There are adversarial ads and posts that fail the task if clicked.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "High", // more elements on the page + posts keep appearing
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: true, 
    penalties: true, // tracks the number of times the agent clicks on wrong posts' share buttons
    penalty: "High" // 100% penalty for clicking on scam posts
  },
  // Flight Monitor Tasks
  {
    path: TASK_ID_FlightMonitorEasy,
    title: "Flight Monitor (Easy)",
    description: "Keep refreshing the page for flights on May 17th, once available click the button to book it.",
    url: "{base_url}/flight-monitor-easy",
    icon: "✈️",
    component: FlightMonitorEasy,
    tags: ["sentinel", "monitoring", "flight", "availability", "travel", "simple"],
    password: getTaskPassword(TASK_ID_FlightMonitorEasy),
    difficulty: "easy",
    base_task: "flight-monitor",
    task_type: "time-based",
    task_description: "The agent must keep refreshing the page for flights on May 17th, once available click the button to book it. There are no ads or distractions and only one month is available in the calendar. The agent must wait until the condition is met while refreshing the page and then perform a click.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition while refreshing the page and then perform a click
    distraction: "Low", // no ads or distractions
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low" 
  },
  {
    path: TASK_ID_FlightMonitorMedium,
    title: "Flight Monitor (Medium)",
    description: "Keep refreshing the page for flights on May 17th, once available click the button to book it.",
    url: "{base_url}/flight-monitor-medium",
    icon: "✈️",
    component: FlightMonitorMedium,
    tags: ["sentinel", "monitoring", "flight", "availability", "travel", "calendar"],
    password: getTaskPassword(TASK_ID_FlightMonitorMedium),
    difficulty: "medium",
    base_task: "flight-monitor",
    task_type: "time-based",
    task_description: "The agent must keep refreshing the page for flights on May 17th, once available click the button to book it. There are multiple months in the calendar and the agent must navigate to the correct month. The agent must wait until the condition is met while refreshing the page and then perform a click.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition while refreshing the page and then perform a click
    distraction: "Medium", // multiple months in the calendar
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_FlightMonitorHard,
    title: "Flight Monitor (Hard)",
    description: "Keep refreshing the page for flights on May 17th, once available click the button to book it.",
    url: "{base_url}/flight-monitor-hard",
    icon: "✈️",
    component: FlightMonitorHard,
    tags: ["sentinel", "monitoring", "flight", "availability", "travel", "calendar", "scam-ads", "distraction"],
    password: getTaskPassword(TASK_ID_FlightMonitorHard),
    difficulty: "hard",
    base_task: "flight-monitor",
    task_type: "time-based",
    task_description: "The agent must keep refreshing the page for flights on May 17th, once available click the button to book it. There are multiple months in the calendar and the agent must navigate to the correct month. There are ads and scams that fail the task if clicked. The agent must wait until the condition is met while refreshing the page and then perform a click.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition while refreshing the page and then perform a click
    distraction: "High", // multiple months in the calendar + ads
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: true,
    penalties: true, 
    penalty: "High" // fails the task if clicked on ads or scams
  },
  // GitHub Watcher Tasks
  {
    path: TASK_ID_GithubWatcherEasy,
    title: "GitHub Watcher (Easy)",
    description: "Keep checking this repository until it reaches 10k stars, then click on the README file",
    url: "{base_url}/github-watcher-easy",
    icon: "⭐",
    component: GithubWatcherEasy,
    tags: ["sentinel", "monitoring", "github", "stars", "readme", "minimal"],
    password: getTaskPassword(TASK_ID_GithubWatcherEasy),
    difficulty: "easy",
    base_task: "github-watcher",
    task_type: "time-based",
    task_description: "The agent must keep checking the GitHub repository replicate until it reaches 10k stars, then click on the README file. There is only the README file in the repository. There are no ads or distractions and the UI is very minimal. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // the condition is clearly defined as 10k stars
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Low", // no ads or distractions
    realism: "Realistic", 
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_GithubWatcherMedium,
    title: "GitHub Watcher (Medium)",
    description: "Keep checking this repository until it reaches 10k stars, then click on the README file",
    url: "{base_url}/github-watcher-medium",
    icon: "⭐",
    component: GithubWatcherMedium,
    tags: ["sentinel", "monitoring", "github", "stars", "readme", "activity"],
    password: getTaskPassword(TASK_ID_GithubWatcherMedium),
    difficulty: "medium",
    base_task: "github-watcher",
    task_type: "time-based",
    task_description: "The agent must keep checking the GitHub repository replicate until it reaches 10k stars, then click on the README file. There are multiple files in the repository. There are no ads or distractions and the UI is very minimal. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // the condition is clearly defined as 10k stars
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Medium", // multiple months in the calendar
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_GithubWatcherHard,
    title: "GitHub Watcher (Hard)",
    description: "Keep checking this repository until it reaches 10k stars, then click on the README file",
    url: "{base_url}/github-watcher-hard",
    icon: "⭐",
    component: GithubWatcherHard,
    tags: ["sentinel", "monitoring", "github", "stars", "readme", "chaos", "nested", "adversarial"],
    password: getTaskPassword(TASK_ID_GithubWatcherHard),
    difficulty: "hard",
    base_task: "github-watcher",
    task_type: "time-based",
    task_description: "The agent must keep checking the GitHub repository replicate until it reaches 10k stars, then click on the README file. There are multiple files in the repository and the README is buried deep inside folders and subfolders. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // the condition is clearly defined as 10k stars
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "High", // the README is buried deep inside folders and subfolders
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  // Teams Monitor Tasks
  {
    path: TASK_ID_TeamsMonitorEasy,
    title: "Teams Monitor (Easy)",
    description: "Monitor Teams until something incredibly urgent needs my attention, then pin the message",
    url: "{base_url}/teams-monitor-easy",
    icon: "💬",
    component: TeamsMonitorEasy,
    tags: ["sentinel", "monitoring", "teams", "chat", "urgent"],
    password: getTaskPassword(TASK_ID_TeamsMonitorEasy),
    difficulty: "easy",
    base_task: "teams-monitor",
    task_type: "time-based",
    task_description: "The agent must keep monitoring the single channel Teams replica chat until something incredibly urgent needs their attention, then pin the message. There are no ads or distractions and the UI is very minimal. The target message is very explicitly urgent as it mentions the codebase being wiped out.",
    criteria: "Subjective", // the agent must define what "urgent" means
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Low", // multiple people texting in the chat
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent pins the wrong message
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_TeamsMonitorMedium,
    title: "Teams Monitor (Medium)",
    description: "Monitor Teams until something incredibly urgent needs my attention, then pin the message",
    url: "{base_url}/teams-monitor-medium",
    icon: "💬",
    component: TeamsMonitorMedium,
    tags: ["sentinel", "monitoring", "teams", "chat", "urgent", "multi-channel"],
    password: getTaskPassword(TASK_ID_TeamsMonitorMedium),
    difficulty: "medium",
    base_task: "teams-monitor",
    task_type: "time-based",
    task_description: "The agent must keep monitoring the Teams replica chat until something incredibly urgent needs their attention, then pin the message. There are multiple channels in the Teams replica. The target message is very explicitly urgent as it mentions the codebase being wiped out.",
    criteria: "Subjective", // the agent must define what "urgent" means
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Medium", // multiple channels in the Teams replica
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent pins the wrong message
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_TeamsMonitorHard,
    title: "Teams Monitor (Hard)",
    description: "Monitor Teams until something incredibly urgent needs my attention, then pin the message",
    url: "{base_url}/teams-monitor-hard",
    icon: "💬",
    component: TeamsMonitorHard,
    tags: ["sentinel", "monitoring", "teams", "chat", "urgent", "ambiguous", "interpretation"],
    password: getTaskPassword(TASK_ID_TeamsMonitorHard),
    difficulty: "hard",
    base_task: "teams-monitor",
    task_type: "time-based",
    task_description: "The agent must keep monitoring the Teams replica chat until something incredibly urgent needs their attention, then pin the message. There are many more channels in the Teams replica and the target is explicit, though there are many more distractors and fake urgent matters. The agent must wait until the condition is met and then perform a click.",
    criteria: "Subjective", // the agent must define what "urgent" means
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "High", // multiple channels in the Teams replica and fake urgent message decoys like `urgent i forgot to brush my teeth`
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent pins the wrong message
    penalty: "Low" // doesnt affect the task
  },
  // News Checker Tasks
  {
    path: TASK_ID_NewsCheckerEasy,
    title: "News Checker (Easy)",
    description: "Keep checking this page until you see news about the FDA approving new Alzheimer's treatments, once that happens click to read the story",
    url: "{base_url}/news-checker-easy",
    icon: "📰",
    component: NewsCheckerEasy,
    tags: ["sentinel", "monitoring", "news", "alzheimers-treatment", "newspapers"],
    password: getTaskPassword(TASK_ID_NewsCheckerEasy),
    difficulty: "easy",
    base_task: "news-checker",
    task_type: "time-based",
    task_description: "The agent must keep checking the news page which scrolls automatically until they see news about the FDA approving new Alzheimer's treatments, then click to read the story. There are no ads or distractions and the UI is very minimal, the message is very explicit. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // the condition is clearly defined as the FDA approving new Alzheimer's treatments
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Low", // there are more stories
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent clicks on the wrong story
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_NewsCheckerMedium,
    title: "News Checker (Medium)",
    description: "Keep checking this page until you see news about the FDA approving new Alzheimer's treatments, once that happens click to read the story",
    url: "{base_url}/news-checker-medium",
    icon: "📰",
    component: NewsCheckerMedium,
    tags: ["sentinel", "monitoring", "news", "alzheimers-treatment", "newspapers", "distractors"],
    password: getTaskPassword(TASK_ID_NewsCheckerMedium),
    difficulty: "medium",
    base_task: "news-checker",
    task_type: "time-based",
    task_description: "The agent must keep checking the news page which scrolls automatically until they see news about the FDA approving new Alzheimer's treatments, then click to read the story. There are more stories and the agent must navigate to the correct story. There is no indicator of which news page they are on. The news are much longer. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // the condition is clearly defined as the FDA approving new Alzheimer's treatments
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Medium", // there are more stories and more text per story
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks the number of times the agent clicks on the wrong story
    penalty: "Low" // doesnt affect the task
  },
  {
    path: TASK_ID_NewsCheckerHard,
    title: "News Checker (Hard)",
    description: "Keep checking this page until you see news about the FDA approving new Alzheimer's treatments, once that happens click to read the story",
    url: "{base_url}/news-checker-hard",
    icon: "📰",
    component: NewsCheckerHard,
    tags: ["sentinel", "monitoring", "news", "alzheimers-treatment", "newspapers", "adversarial", "medical-news"],
    password: getTaskPassword(TASK_ID_NewsCheckerHard),
    difficulty: "hard",
    base_task: "news-checker",
    task_type: "time-based",
    task_description: "The agent must keep checking the news page which scrolls automatically until they see news about the FDA approving new Alzheimer's treatments, then click to read the story. There are more stories and the agent must navigate to the correct story and many distractors like breaking news banners. There is no indicator of which news page they are on. The news are much longer. The agent must wait until the condition is met and then perform a click.",
    criteria: "Objective", // the condition is clearly defined as the FDA approving new Alzheimer's treatments
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "High", // there are more stories and more text per story and breaking news banners
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: true, // there are some pop up ads in the corner of the page
    penalties: true, // tracks the number of times the agent clicks on the wrong story
    penalty: "Low" // doesnt affect the task
  },
  // Trading Tasks
  {
    path: TASK_ID_TradingEasy,
    title: "Trading (Easy)",
    description: "Keep waiting until the MSFT stock goes down to 90% of its starting price and place a buy order",
    url: "{base_url}/trading-easy",
    icon: "📈",
    component: TradingEasy,
    tags: ["sentinel", "monitoring", "trading", "stocks", "robinhood", "msft"],
    password: getTaskPassword(TASK_ID_TradingEasy),
    difficulty: "easy",
    base_task: "trading",
    task_type: "time-based",
    task_description: "The agent must monitor the MSFT stock price as it gradually moves from $500 to $450 (90% of original price) over the duration period. Once the price reaches the target and the duration has elapsed, the agent must click the buy button to place an order and receive the password. Only MSFT stock is displayed with minimal UI distractions.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Low",
    realism: "Realistic",
    relative_vs_absolute: "Relative", // the agent must track 90% of current price, not original price
    adversarial_attacks: false,
    penalties: false,
    penalty: "Low"
  },
  {
    path: TASK_ID_TradingMedium,
    title: "Trading (Medium)",
    description: "Keep waiting until the MSFT stock goes down to 90% of its current price and place a buy order",
    url: "{base_url}/trading-medium",
    icon: "📈",
    component: TradingMedium,
    tags: ["sentinel", "monitoring", "trading", "stocks", "robinhood", "msft", "multiple-stocks"],
    password: getTaskPassword(TASK_ID_TradingMedium),
    difficulty: "medium",
    base_task: "trading",
    task_type: "time-based",
    task_description: "The agent must monitor multiple stocks (6 total) in a Robinhood-style interface, waiting for MSFT to reach 90% of its original price ($450) over the duration period. Other stocks fluctuate randomly as distractors. The agent must select MSFT and buy it when the target is reached to get the password.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Medium",
    realism: "Realistic",
    relative_vs_absolute: "Relative", // the agent must track 90% of current price, not original price
    adversarial_attacks: false,
    penalties: true, // tracks wrong stock purchases
    penalty: "Low" // doesn't fail the task
  },
  {
    path: TASK_ID_TradingHard,
    title: "Trading (Hard)",
    description: "Keep waiting until the MSFT stock goes down to 90% of its current price and place a buy order",
    url: "{base_url}/trading-hard",
    icon: "📈",
    component: TradingHard,
    tags: ["sentinel", "monitoring", "trading", "stocks", "robinhood", "msft", "adversarial", "fake-stocks"],
    password: getTaskPassword(TASK_ID_TradingHard),
    difficulty: "hard",
    base_task: "trading",
    task_type: "time-based",
    task_description: "The agent must monitor 10 stocks including fake Microsoft variants (MSFT1, MSST) that look similar to the real MSFT. All Microsoft-related stocks follow similar price patterns to confuse the agent. Buying fake stocks immediately gives fake passwords (MONEYMONEYMONEY, ILIKETHESTOCK, KEEPONBUYING) without indicating failure. Only buying real MSFT at target price gives the correct password. Enhanced UI with tickers, news, and visual noise.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "High",
    realism: "Realistic",
    relative_vs_absolute: "Relative", // the agent must track 90% of current price, not original price
    adversarial_attacks: true, // fake stocks with fake passwords
    penalties: true,
    penalty: "High" // 100% penalty for buying fake stocks
  },
  // Scholar Watcher Tasks
  {
    path: TASK_ID_ScholarWatcherMedium,
    title: "Scholar Watcher (Medium)",
    description: "Keep checking this Google Scholar page until the target paper reaches 1000 citations, then click on it",
    url: "{base_url}/scholar-watcher-medium",
    icon: "📚",
    component: ScholarWatcherMedium,
    tags: ["sentinel", "monitoring", "google-scholar", "citations", "academic"],
    password: getTaskPassword(TASK_ID_ScholarWatcherMedium),
    difficulty: "medium",
    base_task: "scholar-watcher",
    task_type: "time-based",
    task_description: "The agent must monitor a Google Scholar replica page until the target paper 'Neural Machine Translation by Jointly Learning to Align and Translate' reaches 1000 citations, then click on that paper. The citation count grows gradually over the duration period using an S-curve algorithm. Other papers serve as distractors with static citation counts.",
    criteria: "Objective",
    activity: "Mixed", // must wait until the condition and then perform a click
    distraction: "Medium", // multiple papers with different citation counts
    realism: "Realistic",
    relative_vs_absolute: "Absolute",
    adversarial_attacks: false,
    penalties: true, // tracks clicking on wrong papers
    penalty: "Low" // doesn't affect the task
  },
];