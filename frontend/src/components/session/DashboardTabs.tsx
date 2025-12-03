import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'

export type DashboardTab = 'active' | 'stopped' | 'all'

interface DashboardTabsProps {
  activeTab: DashboardTab
  onTabChange: (tab: DashboardTab) => void
}

const tabs: { id: DashboardTab; label: string }[] = [
  { id: 'active', label: 'Active' },
  { id: 'stopped', label: 'Stopped' },
  { id: 'all', label: 'All' },
]

export function DashboardTabs({ activeTab, onTabChange }: DashboardTabsProps) {
  return (
    <Tabs value={activeTab} onValueChange={(value) => onTabChange(value as DashboardTab)}>
      <TabsList>
        {tabs.map((tab) => (
          <TabsTrigger key={tab.id} value={tab.id}>
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
