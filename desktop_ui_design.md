# TTC-Map Desktop UI Redesign Summary

This document outlines the design concepts, justifications, and trade-offs for a proposed "map-first" desktop interface for the TTC-Map project.

## 1. Desktop Landing View

The landing experience is designed to immediately orient the user geographically while keeping high-level system information accessible.

The original reference image is retained locally pending provenance confirmation.
See the current implementation in [README.md](README.md).

### Design Justifications
- **Map-First Geography:** Using a full-screen, dark-themed geographic base map (rather than a schematic) allows users to instantly understand where stations and live trains are located relative to actual city streets and landmarks.
- **Floating Contextual Panel:** A floating panel on the left (similar to Google Maps or Transit) keeps the map unobstructed. It provides immediate access to route search, overall system status, and quick-links to individual lines without requiring a separate page load.
- **Subtle Live Markers:** Train icons are intentionally kept small and subtle. If the map gets crowded with active trains, large icons would overlap and create visual noise.

### Trade-offs
- **Geographic vs. Schematic Clarity:** A true geographic map can make dense downtown areas (like the "U" of Line 1) feel cramped compared to a heavily distorted schematic map (like the classic TTC map). The trade-off is spatial accuracy over abstract readability.
- **Discoverability:** Floating UI panels can sometimes obscure parts of the map. While the panel is collapsible, users with smaller desktop screens might find it takes up a significant portion of their viewport compared to a traditional top navigation bar.

---

## 2. Route Details View

When a user selects a specific route (e.g., Line 1 Yonge-University), the UI shifts to a focused, progressive disclosure mode.

The original route reference is retained locally pending provenance confirmation.

### Design Justifications
- **Progressive Map Highlighting:** When a route is selected, the map zooms to fit the route's bounding box. Other subway lines are visually de-emphasized (grayed out or lowered in opacity), drawing full attention to the active route and its trains.
- **Vertical Station Timeline:** The side panel transitions from a system overview to a vertical timeline of the selected route. This makes it easy to scan the order of stations, see where trains currently are relative to the stops, and check scheduled departures when available.
- **Clear Route Branding:** The panel header takes on the official color of the selected route (Yellow for Line 1), reinforcing to the user exactly which context they are currently viewing.

### Trade-offs
- **Loss of Global Context:** By visually de-emphasizing the rest of the network, users temporarily lose system-wide situational awareness. If they are looking to plan a trip that involves a transfer to Line 2, the de-emphasized Line 2 might be slightly harder to read until they exit the route-specific view.
- **Vertical Scrolling:** Line 1 has many stations. A vertical list means users will have to scroll to see the entire route's details. An alternative would be a horizontal bottom-drawer timeline, but that would sacrifice vertical map space which is often more valuable on widescreen desktop monitors.
