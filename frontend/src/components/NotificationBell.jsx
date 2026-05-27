import React, { useEffect, useState } from "react";
import api from "../lib/api";
import { Bell } from "lucide-react";
import { Popover, PopoverTrigger, PopoverContent } from "./ui/popover";
import { Link } from "react-router-dom";

export default function NotificationBell() {
  const [items, setItems] = useState([]);
  const [unread, setUnread] = useState(0);

  const load = async () => {
    try {
      const { data } = await api.get("/notifications");
      setItems(data.items || []);
      setUnread(data.unread || 0);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);
    return () => clearInterval(t);
  }, []);

  const markRead = async (id) => {
    await api.post(`/notifications/${id}/read`);
    load();
  };

  const markAll = async () => {
    await api.post(`/notifications/read-all`);
    load();
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button data-testid="notification-bell" className="relative p-2 hover:bg-slate-100 rounded-sm" aria-label="Notifications">
          <Bell size={16} className="text-slate-700" />
          {unread > 0 && (
            <span className="absolute top-0.5 right-0.5 w-4 h-4 text-[9px] font-bold bg-red-600 text-white rounded-full flex items-center justify-center" data-testid="notification-badge">
              {unread > 9 ? "9+" : unread}
            </span>
          )}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="px-3 py-2 border-b border-slate-200 flex items-center justify-between">
          <div className="text-sm font-semibold text-slate-900">Notifications</div>
          {unread > 0 && (
            <button onClick={markAll} className="text-[11px] text-slate-600 hover:text-slate-900" data-testid="notif-mark-all-read">Mark all read</button>
          )}
        </div>
        <div className="max-h-96 overflow-y-auto">
          {items.length === 0 ? (
            <div className="p-4 text-sm text-slate-500" data-testid="notif-empty">No notifications.</div>
          ) : items.map((n) => (
            <div key={n.id} className={`px-3 py-2 border-b border-slate-100 ${!n.read ? "bg-blue-50/40" : ""}`} data-testid={`notif-${n.id}`}>
              <div className="flex items-start gap-2">
                {!n.read && <div className="w-1.5 h-1.5 rounded-full bg-blue-600 mt-1.5" />}
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-slate-900">{n.title}</div>
                  <div className="text-xs text-slate-600 mt-0.5 line-clamp-2">{n.body}</div>
                  <div className="text-[10px] text-slate-400 mono mt-1 flex items-center gap-2">
                    <span>{new Date(n.timestamp).toLocaleString()}</span>
                    {n.link && <Link to={n.link} onClick={() => markRead(n.id)} className="text-slate-700 hover:text-slate-900 underline-offset-2 hover:underline">Open</Link>}
                    {!n.read && <button onClick={() => markRead(n.id)} className="text-slate-700 hover:text-slate-900">Mark read</button>}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
