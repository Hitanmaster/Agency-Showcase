const axios = require('axios');
const cheerio = require('cheerio'); // 🧼 jQuery-like HTML parser

async function scrapeKoto() {
  const url = 'https://koto.studio/work';
  const { data: html } = await axios.get(url); // 🛰 Fetch page
  const $ = cheerio.load(html);                // 🧼 Load DOM

  const projects = [];

  // Target each project item on the page
  $('.project-item').each((_, el) => {
    // Extract the project URL (href)
    const href = $(el).find('a').attr('href');
    
    // Extract the video URL (data-work-page-thumbnail-video)
    const videoUrl = $(el).find('a').attr('data-work-page-thumbnail-video');

    // Extract the title
    const title = $(el).find('.work-meta h2').text().trim();

    // Push project data into the array
    projects.push({
      title,
      url: `https://koto.studio${href}`,
      videoUrl,
      source: 'koto.studio'
    });
  });

  return projects;
}

module.exports = scrapeKoto;
