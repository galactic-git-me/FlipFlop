"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Bell, X, CheckCircle2, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface Notification {
  id: string;
  type: "sale" | "error" | "info";
  title: string;
  message: string;
  details?: {
    flipId?: number;
    salePrice?: number;
    profit?: number;
    buyerId?: string;
  };
  timestamp: Date;
  read: boolean;
}

export function SalesNotificationCenter() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  // Simulate receiving notifications (in real app, would use WebSocket)
  useEffect(() => {
    const handleSaleNotification = (event: any) => {
      const notification: Notification = {
        id: `notif-${Date.now()}`,
        type: event.detail?.type || "sale",
        title: event.detail?.title || "Sale Alert",
        message: event.detail?.message || "",
        details: event.detail?.details,
        timestamp: new Date(),
        read: false,
      };

      setNotifications((prev) => [notification, ...prev]);

      // Show browser notification if permitted
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(notification.title, {
          body: notification.message,
          icon: "/flipflop-icon.png",
          tag: "sales",
          requireInteraction: true,
        });
      }
    };

    window.addEventListener("sale-notification", handleSaleNotification);
    return () => window.removeEventListener("sale-notification", handleSaleNotification);
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleMarkAsRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  }, []);

  const handleClearAll = useCallback(() => {
    setNotifications([]);
  }, []);

  const handleDismiss = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  return (
    <div className="relative">
      {/* Bell Icon Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-slate-400 hover:text-slate-200 transition"
        title="Sales notifications"
      >
        <Bell className="w-5 h-5" />
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 w-2 h-2 bg-emerald-400 rounded-full animate-pulse" />
        )}
      </button>

      {/* Notification Panel */}
      {isOpen && (
        <div className="absolute right-0 top-10 w-96 bg-[#0d1320] border border-[#1e2d45] rounded-lg shadow-xl z-50">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-[#1e2d45]">
            <div>
              <h3 className="font-semibold text-slate-100">Notifications</h3>
              {unreadCount > 0 && (
                <p className="text-xs text-emerald-400">
                  {unreadCount} new notification{unreadCount !== 1 ? "s" : ""}
                </p>
              )}
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-slate-200"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Notifications List */}
          <div className="max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-8 text-center">
                <Bell className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No notifications yet</p>
              </div>
            ) : (
              <div className="divide-y divide-[#1e2d45]">
                {notifications.map((notif) => (
                  <NotificationItem
                    key={notif.id}
                    notification={notif}
                    onMarkAsRead={() => handleMarkAsRead(notif.id)}
                    onDismiss={() => handleDismiss(notif.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="p-3 border-t border-[#1e2d45] text-center">
              <button
                onClick={handleClearAll}
                className="text-xs text-slate-500 hover:text-slate-400 transition"
              >
                Clear all
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NotificationItem({
  notification,
  onMarkAsRead,
  onDismiss,
}: {
  notification: Notification;
  onMarkAsRead: () => void;
  onDismiss: () => void;
}) {
  const icon =
    notification.type === "sale" ? (
      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
    ) : (
      <AlertCircle className="w-5 h-5 text-yellow-400" />
    );

  const bgColor =
    notification.type === "sale"
      ? "bg-emerald-400/10 border-emerald-400/20 hover:bg-emerald-400/15"
      : "bg-yellow-400/10 border-yellow-400/20 hover:bg-yellow-400/15";

  return (
    <div
      className={cn(
        "p-4 border-b border-[#1e2d45] hover:bg-[#0a0f1a]/50 transition cursor-pointer",
        !notification.read && "bg-[#0a0f1a]"
      )}
      onClick={onMarkAsRead}
    >
      <div className="flex items-start gap-3">
        <div className="flex-shrink-0 mt-0.5">{icon}</div>

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className="font-semibold text-slate-200 text-sm">
              {notification.title}
            </h4>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDismiss();
              }}
              className="text-slate-500 hover:text-slate-400 flex-shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <p className="text-sm text-slate-400 mt-1">{notification.message}</p>

          {notification.details && notification.type === "sale" && (
            <div className="mt-3 p-2 bg-[#0a0f1a] rounded border border-emerald-400/20 space-y-1">
              {notification.details.profit && (
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Profit:</span>
                  <span className="text-emerald-400 font-semibold">
                    +£{notification.details.profit.toFixed(0)}
                  </span>
                </div>
              )}
              {notification.details.salePrice && (
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Sale Price:</span>
                  <span className="text-slate-200">
                    £{notification.details.salePrice.toFixed(0)}
                  </span>
                </div>
              )}
              {notification.details.buyerId && (
                <div className="flex justify-between text-xs">
                  <span className="text-slate-500">Buyer:</span>
                  <span className="text-slate-300 font-mono">
                    {notification.details.buyerId}
                  </span>
                </div>
              )}
            </div>
          )}

          <div className="mt-2 text-xs text-slate-600">
            {getTimeAgo(notification.timestamp)}
          </div>

          {!notification.read && (
            <div className="mt-2 inline-block">
              <span className="px-2 py-1 bg-emerald-400/20 text-emerald-400 text-xs rounded">
                New
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function getTimeAgo(date: Date): string {
  const now = new Date();
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;

  const days = Math.floor(seconds / 86400);
  return `${days}d ago`;
}

// Utility function to send notifications from elsewhere in the app
export function sendSaleNotification(details: {
  title: string;
  flipTitle: string;
  salePrice: number;
  profit: number;
  buyerId: string;
}) {
  const event = new CustomEvent("sale-notification", {
    detail: {
      type: "sale",
      title: "🎉 " + details.title,
      message: `${details.flipTitle} sold for £${details.salePrice.toFixed(0)}`,
      details: {
        salePrice: details.salePrice,
        profit: details.profit,
        buyerId: details.buyerId,
      },
    },
  });

  window.dispatchEvent(event);
}
