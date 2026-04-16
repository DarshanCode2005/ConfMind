/**
 * frontend/lib/mock-data.ts — Mock AgentState for frontend development without backend.
 * 
 * This file provides realistic sample data for all agent outputs.
 * Enable by setting NEXT_PUBLIC_USE_MOCK_DATA=true in .env.local
 */

import type { AgentState } from "./api";

export const mockAgentState: AgentState = {
  plan_id: "demo-plan-2026-04-16",
  status: "completed",

  // Sponsor Agent Results
  sponsors: [
    {
      name: "TechCorp Inc",
      tier: "Gold",
      website: "https://techcorp.com",
      industry: "Software",
      geo: "North America",
      relevance_score: 9.5,
    },
    {
      name: "CloudScale Systems",
      tier: "Gold",
      website: "https://cloudscale.io",
      industry: "Cloud Infrastructure",
      geo: "Europe",
      relevance_score: 9.2,
    },
    {
      name: "DataVault Analytics",
      tier: "Silver",
      website: "https://datavault.ai",
      industry: "Data & Analytics",
      geo: "North America",
      relevance_score: 8.7,
    },
    {
      name: "SecureNet Pro",
      tier: "Silver",
      website: "https://securenet.pro",
      industry: "Cybersecurity",
      geo: "Global",
      relevance_score: 8.3,
    },
    {
      name: "DevTools Studio",
      tier: "Bronze",
      website: "https://devtools.studio",
      industry: "Developer Tools",
      geo: "North America",
      relevance_score: 7.8,
    },
    {
      name: "APIFirst Labs",
      tier: "Bronze",
      website: "https://apifirst.labs",
      industry: "API Management",
      geo: "Europe",
      relevance_score: 7.5,
    },
  ],

  // Speaker Agent Results
  speakers: [
    {
      name: "Alice Chen",
      bio: "Principal Engineer at TechCorp, 15+ years in distributed systems",
      linkedin_url: "https://linkedin.com/in/alicechen",
      topic: "Scaling Microservices at 10M Requests/sec",
      region: "San Francisco, CA",
      influence_score: 9.8,
      speaking_experience: 24,
    },
    {
      name: "Marcus Johnson",
      bio: "VP of Engineering, recognized cloud architect",
      linkedin_url: "https://linkedin.com/in/mjohnson",
      topic: "Cloud Migration Strategies for Enterprise",
      region: "Seattle, WA",
      influence_score: 9.5,
      speaking_experience: 18,
    },
    {
      name: "Priya Patel",
      bio: "Security researcher and author of 3 technical books",
      linkedin_url: "https://linkedin.com/in/priyapatel",
      topic: "Zero-Trust Architecture in 2026",
      region: "London, UK",
      influence_score: 9.2,
      speaking_experience: 21,
    },
    {
      name: "David Kim",
      bio: "AI/ML specialist, published 40+ research papers",
      linkedin_url: "https://linkedin.com/in/davidkim",
      topic: "LLM Optimization for Edge Deployment",
      region: "Seoul, Korea",
      influence_score: 8.9,
      speaking_experience: 15,
    },
    {
      name: "Elena Rodriguez",
      bio: "Product Lead at CloudScale, focus on developer experience",
      linkedin_url: "https://linkedin.com/in/erodriguez",
      topic: "Building Developer-First Products",
      region: "Austin, TX",
      influence_score: 8.6,
      speaking_experience: 12,
    },
    {
      name: "James Thompson",
      bio: "Open-source maintainer, 50K+ GitHub followers",
      linkedin_url: "https://linkedin.com/in/jthompson",
      topic: "The Future of Open Source Governance",
      region: "Portland, OR",
      influence_score: 8.3,
      speaking_experience: 9,
    },
  ],

  // Venue Agent Results
  venues: [
    {
      name: "Convention Center Downtown",
      city: "San Francisco",
      country: "USA",
      capacity: 5000,
      price_range: "$50k - $150k",
      score: 9.7,
      source_url: "https://sfconventioncenter.com",
      past_events: ["Tech Summit 2025", "Cloud Conference 2024"],
    },
    {
      name: "Moscone Center",
      city: "San Francisco",
      country: "USA",
      capacity: 4000,
      price_range: "$60k - $180k",
      score: 9.5,
      source_url: "https://moscone.com",
      past_events: ["DevCon 2025", "OpenStack Days 2024"],
    },
    {
      name: "Seattle Convention Center",
      city: "Seattle",
      country: "USA",
      capacity: 3500,
      price_range: "$40k - $120k",
      score: 9.1,
      source_url: "https://seattlecc.com",
      past_events: ["AWS Summit 2024"],
    },
    {
      name: "ExCel London",
      city: "London",
      country: "UK",
      capacity: 6000,
      price_range: "$80k - $200k",
      score: 8.9,
      source_url: "https://excel.london",
      past_events: ["CloudExpo Europe 2024", "InfoSecurity Europe 2024"],
    },
  ],

  // Exhibitor Agent Results
  exhibitors: [
    {
      name: "MongoDB",
      cluster: "Database & Storage",
      relevance: 9.3,
      website: "https://mongodb.com",
    },
    {
      name: "Datadog",
      cluster: "Monitoring & Observability",
      relevance: 9.1,
      website: "https://datadog.com",
    },
    {
      name: "HashiCorp",
      cluster: "Infrastructure as Code",
      relevance: 8.8,
      website: "https://hashicorp.com",
    },
    {
      name: "JetBrains",
      cluster: "Developer Tools",
      relevance: 8.5,
      website: "https://jetbrains.com",
    },
    {
      name: "Auth0",
      cluster: "Identity & Security",
      relevance: 8.2,
      website: "https://auth0.com",
    },
  ],

  // Pricing Agent Results
  ticket_tiers: [
    {
      name: "Early Bird",
      price: 299,
      est_sales: 500,
      revenue: 149500,
    },
    {
      name: "General",
      price: 499,
      est_sales: 1200,
      revenue: 598800,
    },
    {
      name: "VIP",
      price: 899,
      est_sales: 200,
      revenue: 179800,
    },
  ],

  // Event Ops Agent Results
  schedule: [
    {
      time: "09:00 AM",
      room: "Main Hall",
      speaker: "Alice Chen",
      topic: "Scaling Microservices at 10M Requests/sec",
    },
    {
      time: "10:00 AM",
      room: "Track A",
      speaker: "Marcus Johnson",
      topic: "Cloud Migration Strategies for Enterprise",
    },
    {
      time: "10:00 AM",
      room: "Track B",
      topic: "Workshop: Kubernetes Advanced Patterns",
    },
    {
      time: "11:15 AM",
      room: "Main Hall",
      speaker: "Priya Patel",
      topic: "Zero-Trust Architecture in 2026",
    },
    {
      time: "12:30 PM",
      room: "Networking Area",
      topic: "Lunch & Networking",
    },
    {
      time: "01:30 PM",
      room: "Main Hall",
      speaker: "David Kim",
      topic: "LLM Optimization for Edge Deployment",
    },
    {
      time: "02:30 PM",
      room: "Track A",
      speaker: "Elena Rodriguez",
      topic: "Building Developer-First Products",
    },
    {
      time: "02:30 PM",
      room: "Track B",
      topic: "Panel: Future of Cloud Computing",
    },
    {
      time: "03:45 PM",
      room: "Main Hall",
      speaker: "James Thompson",
      topic: "The Future of Open Source Governance",
    },
    {
      time: "04:45 PM",
      room: "Main Hall",
      topic: "Closing Remarks & Networking",
    },
  ],

  // Community GTM Agent Results
  communities: [
    {
      platform: "Discord",
      name: "DevOps Engineers Community",
      size: 12500,
      niche: "DevOps & Infrastructure",
      invite_url: "https://discord.gg/devops",
    },
    {
      platform: "Discord",
      name: "Cloud Native Developers",
      size: 18900,
      niche: "Cloud Native & Kubernetes",
      invite_url: "https://discord.gg/cloudnative",
    },
    {
      platform: "Slack",
      name: "Enterprise Architecture Leaders",
      size: 5600,
      niche: "Enterprise & Architecture",
      invite_url: "https://slack.com/enterprise-arch",
    },
    {
      platform: "LinkedIn",
      name: "Cloud Computing Professionals",
      size: 342000,
      niche: "Professional Network",
      invite_url: "https://linkedin.com/groups/cloud-pros",
    },
  ],

  gtm_messages: {
    Discord:
      "🚀 Join us at Tech Summit 2026 in San Francisco! Connect with 5000+ developers, learn from industry leaders, and explore cutting-edge cloud technologies. Early bird tickets 50% off until April 30.",
    Slack:
      "📢 Exciting announcement! Enterprise leaders share insights on scalable architecture, zero-trust security, and cloud migration best practices at our conference.",
    LinkedIn:
      "Connect with 1500+ technical leaders discussing the future of cloud computing, microservices, and AI/ML at our flagship developer conference.",
  },

  distribution_plan: [
    "Post Discord invitations in 50+ DevOps and cloud communities starting Week 1",
    "Launch Slack outreach campaign targeting enterprise architecture channels by Week 2",
    "Share LinkedIn announcements and personal outreach from 20+ speaker networks by Week 3",
    "Email campaigns to 100K+ developer mailing lists with early bird CTAs starting Week 2",
    "Partner with TechCorp and CloudScale for cross-promotion on their platforms",
    "Execute Twitter/X campaign with #DevConf2026 hashtag reaching 500K+ impressions",
  ],

  total_est_revenue: 928100,
  break_even_price: 189,

  conflicts: [],
  errors: [],
};
