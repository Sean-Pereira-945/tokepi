# DriftGuard Dashboard: A Beginner's Guide

Welcome to the **DriftGuard Dashboard**! Think of this as the control center for your AI applications. It helps you easily monitor how well your AI is performing, whether it is making mistakes, or if it is wasting money. 

This guide explains all the key features of the dashboard in plain, easy-to-understand language.

---

## 1. The Big Picture (Overview Metrics)

At the top of your dashboard, you will see a quick summary of how your AI is doing right now:

* **Total Telemetry Events:** This simply means "How many times was the AI used recently?" It gives you a sense of how busy your application is.
* **Saved Tokens / Cost:** Every time the AI reads or writes a word, it uses "tokens", which cost money. This number shows how much money DriftGuard has saved you by catching bad or repetitive behavior.
* **Active / Critical Alerts:** If your AI starts acting strangely or making poor decisions, an alert will pop up here. "Critical" means it needs your attention immediately.
* **Mean Retrieval Score (Relevance):** This is a score from 0 to 1 that tells you how relevant the information fed to the AI is. A score closer to 1 means the AI is getting high-quality, relevant information to do its job.

---

## 2. Visualizing Performance (Charts)

We use visual charts to make it easy to spot trends and issues at a glance.

* **Telemetry & Drift Timeline:** This line graph shows you if things are changing over time. For example, you might see that the AI is suddenly reading a lot more text (using more tokens), but the quality of its answers is dropping. This is a clear sign something is wrong.
* **Drift Risk Breakdown (Radar Chart):** This chart highlights where your biggest risks are. It flags issues like:
    * **Prompt Drift:** The instructions given to the AI are getting too long or changing unexpectedly.
    * **Quality Loss:** The AI's answers are getting worse.
    * **Context Bloat:** The AI is being forced to read way too much information at once.
* **Context Length Distribution:** A visual representation of how much information (context) the AI is reading for each task. If it's constantly reading huge amounts of text, it might get confused or cost more money.
* **Tokens vs Quality Correlation:** Does spending more money actually make the AI smarter? This chart compares how much you are spending (tokens) against the quality of the AI's answers. If you are spending a lot but quality is low, it's time to investigate.

---

## 3. Alerts & Warnings

DriftGuard acts like an alarm system for your AI. It categorizes its observations into three levels:

* 🟢 **Stable:** Everything is running smoothly. Relax!
* 🟡 **Warning:** Something looks a little off. You should probably check it out before it becomes a bigger issue or starts costing you money.
* 🔴 **Critical:** The AI is making significant mistakes, wasting a lot of money, or behaving way outside its normal boundaries. You need to investigate this right away.

---

## 4. AI Agent Tracking (Why did the AI get stuck?)

Sometimes, AI agents are asked to perform complex tasks (like writing code or searching the web). If they get stuck, they might try the same failing action over and over again, wasting time and money.

The dashboard includes an **Agent Task Diagnosis** section that shows you:
* Exactly what task the AI was trying to do.
* Which tool it was trying to use when it failed.
* How many times it repeated the same mistake.
* The error message explaining why it failed.

This helps you quickly figure out why your AI is stuck and stop it from wasting more resources.

---

## 5. Controls at the Top (Header)

* **Project:** If you have multiple AI apps, you can switch between them here.
* **Environment:** Lets you see data for different versions of your app (e.g., the "Testing" version vs. the "Live/Production" version).
* **Refresh:** Grabs the absolute latest data so you are always looking at real-time information.
