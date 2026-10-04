# JobSync-AWS

## Cache-Aware Event-Driven Job Synchronization and Personalized Job Discovery Using AWS

A cloud-native job synchronization and discovery system that collects job listings from multiple sources, detects meaningful changes, removes duplicates, and processes only the data that actually changed.

The core principle of the system is:

> **Don't process what hasn't changed.**

## 🚀 Live Application

**Frontend:**  
https://madesh405.github.io/JobSync-AWS/

**Backend API:**  
https://cviwg4d4h2.execute-api.us-east-1.amazonaws.com/jobs

## 📌 Problem

Job information is distributed across multiple job sources and changes continuously.

A traditional approach repeatedly:

```text
Fetch everything
      ↓
Process everything
      ↓
Store everything
      ↓
Process again
