const express = require('express');
const cors = require('cors');
const scrapeAll = require('./scrapers');
const fs = require('fs');
const cron = require('node-cron');

const app = express();
app.use(cors());

const dataPath = './data/projects.json';

// Load existing data
function loadProjects() {
  if (!fs.existsSync(dataPath)) return [];
  const raw = fs.readFileSync(dataPath);
  return JSON.parse(raw);
}

// Save data
function saveProjects(projects) {
  fs.writeFileSync(dataPath, JSON.stringify(projects, null, 2));
}

// API to get all projects
app.get('/api/projects', (req, res) => {
  const projects = loadProjects();
  res.json(projects);
});

// Scrape and store new projects
app.get('/api/scrape', async (req, res) => {
  const existing = loadProjects();
  const newOnes = await scrapeAll();

  const newEntries = newOnes.filter(
    np => !existing.some(ep => ep.url === np.url)
  );

  const combined = [...newEntries, ...existing];
  saveProjects(combined);

  res.json({ added: newEntries.length });
});

// Run scrape daily at 3AM
cron.schedule('0 3 * * *', async () => {
  const existing = loadProjects();
  const newOnes = await scrapeAll();
  const newEntries = newOnes.filter(
    np => !existing.some(ep => ep.url === np.url)
  );
  const combined = [...newEntries, ...existing];
  saveProjects(combined);
  console.log(`🕒 Cron: Added ${newEntries.length} new projects`);
});

app.listen(3001, () => console.log('✅ Backend running on http://localhost:3001'));
