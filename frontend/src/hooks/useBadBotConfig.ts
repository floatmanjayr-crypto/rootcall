import { useState, useEffect } from 'react';
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
