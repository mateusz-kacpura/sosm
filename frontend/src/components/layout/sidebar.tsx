"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard,
  Users,
  Megaphone,
  History,
  Fingerprint,
  Monitor,
  LogOut
} from "lucide-react"
import { cn } from "@/lib/utils"
import { useAuth } from "@/components/auth/auth-provider"

const menuItems = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Konta FB", href: "/accounts", icon: Users },
  { name: "Kampanie", href: "/campaigns", icon: Megaphone },
  { name: "Historia Logów", href: "/logs", icon: History },
  { name: "Fingerprint Test", href: "/fingerprint-test", icon: Fingerprint },
  { name: "System", href: "/system", icon: Monitor },
]

export function Sidebar() {
  const pathname = usePathname()
  const { logout } = useAuth()

  return (
    <div className="flex h-screen w-64 flex-col border-r bg-card text-card-foreground">
      <div className="flex h-16 items-center justify-center border-b px-4">
        <h1 className="text-xl font-bold text-primary tracking-tighter">SOSM Panel</h1>
      </div>
      <nav className="flex-1 space-y-1 p-4">
        {menuItems.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center space-x-3 rounded-lg px-3 py-2 transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground font-medium"
                  : "hover:bg-secondary hover:text-foreground"
              )}
            >
              <item.icon className="h-5 w-5" />
              <span>{item.name}</span>
            </Link>
          )
        })}
      </nav>
      <div className="border-t p-4">
        <button
          onClick={logout}
          className="flex w-full items-center space-x-3 rounded-lg px-3 py-2 text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors cursor-pointer"
        >
          <LogOut className="h-5 w-5" />
          <span>Wyloguj</span>
        </button>
      </div>
    </div>
  )
}
