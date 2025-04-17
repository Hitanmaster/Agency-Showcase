const scrapeKoto = require('./koto');

async function scrapeAll() {
  const kotoProjects = await scrapeKoto();
  return kotoProjects;
}

module.exports = scrapeAll;
