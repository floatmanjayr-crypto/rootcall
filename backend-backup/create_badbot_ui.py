# -*- coding: utf-8 -*-
"""
Create BadBot Client Portal UI
Complete dashboard for managing call screening
"""
import os

print("="*60)
print("CREATING BADBOT CLIENT PORTAL")
print("="*60)

# Create frontend directory structure
os.makedirs('../frontend/src/pages/badbot', exist_ok=True)
os.makedirs('../frontend/src/components/badbot', exist_ok=True)
os.makedirs('../frontend/src/hooks', exist_ok=True)

print("\n1. Creating BadBot Dashboard Page...")

# Main BadBot Dashboard
dashboard_code = '''import React, { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Shield, Phone, Users, Settings, TrendingUp, AlertTriangle } from 'lucide-react';
import { useBadBotConfig } from '@/hooks/useBadBotConfig';

export default function BadBotDashboard() {
  const { config, stats, loading, updateConfig } = useBadBotConfig();

  if (loading) {
    return <div className="flex items-center justify-center h-screen">
      <div className="text-lg">Loading your BadBot protection...</div>
    </div>;
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold flex items-center gap-2">
            <Shield className="text-blue-600" />
            BadBot Protection
          </h1>
          <p className="text-gray-600 mt-1">
            AI-powered call screening for {config?.client_name}
          </p>
        </div>
        <Badge variant={config?.is_active ? "success" : "secondary"}>
          {config?.is_active ? "Active" : "Inactive"}
        </Badge>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard 
          icon={<AlertTriangle className="text-red-500" />}
          title="Spam Blocked"
          value={stats?.spam_blocked || 0}
          subtitle="This month"
        />
        <StatCard 
          icon={<Phone className="text-blue-500" />}
          title="Calls Screened"
          value={stats?.calls_screened || 0}
          subtitle="This month"
        />
        <StatCard 
          icon={<Users className="text-green-500" />}
          title="Trusted Contacts"
          value={config?.trusted_contacts?.length || 0}
          subtitle="Direct connect"
        />
        <StatCard 
          icon={<TrendingUp className="text-purple-500" />}
          title="Success Rate"
          value={stats?.success_rate || "98%"}
          subtitle="Accuracy"
        />
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Configuration Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings />
              Protection Settings
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ConfigOption
              label="SMS Alerts"
              description="Get notified about blocked spam and unknown callers"
              enabled={config?.sms_alerts_enabled}
              onChange={(val) => updateConfig({ sms_alerts_enabled: val })}
            />
            <ConfigOption
              label="Alert on Spam"
              description="Receive SMS when spam calls are blocked"
              enabled={config?.alert_on_spam}
              onChange={(val) => updateConfig({ alert_on_spam: val })}
            />
            <ConfigOption
              label="Alert on Unknown"
              description="Get notified when unknown callers are screened"
              enabled={config?.alert_on_unknown}
              onChange={(val) => updateConfig({ alert_on_unknown: val })}
            />
            <ConfigOption
              label="Auto-Block Spam"
              description="Automatically block known spam numbers"
              enabled={config?.auto_block_spam}
              onChange={(val) => updateConfig({ auto_block_spam: val })}
            />
          </CardContent>
        </Card>

        {/* Trusted Contacts Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users />
              Trusted Contacts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <TrustedContactsList 
              contacts={config?.trusted_contacts || []}
              onAdd={(phone) => {/* Add contact */}}
              onRemove={(phone) => {/* Remove contact */}}
            />
          </CardContent>
        </Card>

        {/* Recent Activity */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Recent Call Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <RecentCallsTable calls={stats?.recent_calls || []} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function StatCard({ icon, title, value, subtitle }) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-600">{title}</p>
            <p className="text-3xl font-bold mt-2">{value}</p>
            <p className="text-xs text-gray-500 mt-1">{subtitle}</p>
          </div>
          <div className="text-4xl">{icon}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function ConfigOption({ label, description, enabled, onChange }) {
  return (
    <div className="flex items-center justify-between p-3 border rounded-lg">
      <div>
        <p className="font-medium">{label}</p>
        <p className="text-sm text-gray-600">{description}</p>
      </div>
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
      </label>
    </div>
  );
}

function TrustedContactsList({ contacts, onAdd, onRemove }) {
  const [newContact, setNewContact] = useState('');

  return (
    <div className="space-y-3">
      {contacts.map((contact, idx) => (
        <div key={idx} className="flex items-center justify-between p-2 bg-gray-50 rounded">
          <span className="font-mono">{contact}</span>
          <Button 
            variant="ghost" 
            size="sm" 
            onClick={() => onRemove(contact)}
            className="text-red-600"
          >
            Remove
          </Button>
        </div>
      ))}
      <div className="flex gap-2">
        <input
          type="tel"
          placeholder="+1234567890"
          value={newContact}
          onChange={(e) => setNewContact(e.target.value)}
          className="flex-1 px-3 py-2 border rounded"
        />
        <Button onClick={() => {
          onAdd(newContact);
          setNewContact('');
        }}>
          Add
        </Button>
      </div>
    </div>
  );
}

function RecentCallsTable({ calls }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b">
            <th className="text-left p-3">Time</th>
            <th className="text-left p-3">From</th>
            <th className="text-left p-3">Status</th>
            <th className="text-left p-3">Action</th>
          </tr>
        </thead>
        <tbody>
          {calls.length === 0 ? (
            <tr>
              <td colSpan="4" className="text-center p-6 text-gray-500">
                No recent calls
              </td>
            </tr>
          ) : (
            calls.map((call, idx) => (
              <tr key={idx} className="border-b hover:bg-gray-50">
                <td className="p-3">{new Date(call.timestamp).toLocaleString()}</td>
                <td className="p-3 font-mono">{call.from}</td>
                <td className="p-3">
                  <Badge variant={
                    call.status === 'blocked' ? 'destructive' :
                    call.status === 'transferred' ? 'success' : 'secondary'
                  }>
                    {call.status}
                  </Badge>
                </td>
                <td className="p-3 text-sm text-gray-600">{call.action}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
'''

with open('../frontend/src/pages/badbot/Dashboard.tsx', 'w') as f:
    f.write(dashboard_code)

print("✓ Created Dashboard.tsx")

print("\n2. Creating BadBot API Hook...")

# Create custom hook for BadBot API
hook_code = '''import { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useBadBotConfig() {
  const [config, setConfig] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchConfig();
    fetchStats();
  }, []);

  const fetchConfig = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/badbot/config`);
      setConfig(response.data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/badbot/stats`);
      setStats(response.data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  const updateConfig = async (updates) => {
    try {
      const response = await axios.patch(`${API_URL}/api/badbot/config`, updates);
      setConfig(response.data);
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  const addTrustedContact = async (phoneNumber) => {
    try {
      await axios.post(`${API_URL}/api/badbot/trusted-contacts`, {
        phone_number: phoneNumber
      });
      fetchConfig();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  const removeTrustedContact = async (phoneNumber) => {
    try {
      await axios.delete(`${API_URL}/api/badbot/trusted-contacts/${phoneNumber}`);
      fetchConfig();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  return {
    config,
    stats,
    loading,
    error,
    updateConfig,
    addTrustedContact,
    removeTrustedContact,
    refresh: fetchConfig
  };
}
'''

with open('../frontend/src/hooks/useBadBotConfig.ts', 'w') as f:
    f.write(hook_code)

print("✓ Created useBadBotConfig.ts")

print("\n3. Creating Backend API Endpoints...")

# Create BadBot API router
api_code = '''from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.badbot_config import BadBotConfig
from app.models.phone_number import PhoneNumber
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/badbot", tags=["BadBot API"])

class ConfigUpdate(BaseModel):
    sms_alerts_enabled: Optional[bool] = None
    alert_on_spam: Optional[bool] = None
    alert_on_unknown: Optional[bool] = None
    auto_block_spam: Optional[bool] = None

class TrustedContactAdd(BaseModel):
    phone_number: str

@router.get("/config")
async def get_config(db: Session = Depends(get_db)):
    """Get BadBot configuration for current user"""
    # TODO: Get user_id from auth token
    user_id = 1  # Placeholder
    
    config = db.query(BadBotConfig).filter(
        BadBotConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    return {
        "client_name": config.client_name,
        "client_cell": config.client_cell,
        "trusted_contacts": config.trusted_contacts or [],
        "sms_alerts_enabled": config.sms_alerts_enabled,
        "alert_on_spam": config.alert_on_spam,
        "alert_on_unknown": config.alert_on_unknown,
        "auto_block_spam": config.auto_block_spam,
        "is_active": config.is_active
    }

@router.patch("/config")
async def update_config(
    updates: ConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update BadBot configuration"""
    user_id = 1  # Placeholder
    
    config = db.query(BadBotConfig).filter(
        BadBotConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    # Update fields
    for field, value in updates.dict(exclude_unset=True).items():
        setattr(config, field, value)
    
    db.commit()
    db.refresh(config)
    
    return {"success": True, "config": config}

@router.get("/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get BadBot statistics"""
    # TODO: Implement actual stats from call logs
    return {
        "spam_blocked": 42,
        "calls_screened": 156,
        "success_rate": "98%",
        "recent_calls": []
    }

@router.post("/trusted-contacts")
async def add_trusted_contact(
    contact: TrustedContactAdd,
    db: Session = Depends(get_db)
):
    """Add trusted contact"""
    user_id = 1
    
    config = db.query(BadBotConfig).filter(
        BadBotConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if config.trusted_contacts is None:
        config.trusted_contacts = []
    
    if contact.phone_number not in config.trusted_contacts:
        config.trusted_contacts.append(contact.phone_number)
        db.commit()
    
    return {"success": True}

@router.delete("/trusted-contacts/{phone_number}")
async def remove_trusted_contact(
    phone_number: str,
    db: Session = Depends(get_db)
):
    """Remove trusted contact"""
    user_id = 1
    
    config = db.query(BadBotConfig).filter(
        BadBotConfig.user_id == user_id
    ).first()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    if config.trusted_contacts and phone_number in config.trusted_contacts:
        config.trusted_contacts.remove(phone_number)
        db.commit()
    
    return {"success": True}
'''

os.makedirs('app/routers', exist_ok=True)
with open('app/routers/badbot_api.py', 'w') as f:
    f.write(api_code)

print("✓ Created badbot_api.py")

print("\n" + "="*60)
print("BADBOT CLIENT PORTAL CREATED!")
print("="*60)
print("\nFiles created:")
print("  Frontend:")
print("    - frontend/src/pages/badbot/Dashboard.tsx")
print("    - frontend/src/hooks/useBadBotConfig.ts")
print("  Backend:")
print("    - app/routers/badbot_api.py")
print("\nNext steps:")
print("  1. Add router to main.py:")
print("     from app.routers.badbot_api import router as badbot_api_router")
print("     app.include_router(badbot_api_router)")
print("  2. Start frontend dev server")
print("  3. Navigate to /badbot/dashboard")
print("="*60)

