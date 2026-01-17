---
title: Linking LH
emoji: 🔗
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
license: mit
app_port: 7860
---

# JSON Link Viewer & Editor

A collaborative web application for reviewing and editing JSON link data between Likutei Halakhot and Likutei Moharan.

## Features

- 🔄 Real-time collaborative editing with conflict detection
- 👥 Multi-user support with change tracking
- 📝 Intuitive web interface for reviewing links
- 🔒 Simple authentication for admin functions

## Usage

1. Enter your username when prompted
2. Review and edit link data
3. Changes are saved automatically to the server
4. Multiple users can work simultaneously with conflict detection

## Admin Functions

Users with admin access (configured via `ADMIN_USER` environment variable) can:
- Upload new JSON files
- Download current data

Default admin user: `danny`
