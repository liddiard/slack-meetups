const width = window.innerWidth,
  height = window.innerWidth;
      
async function main() {
  // make API request to get pool data
  const pathParts = window.location.pathname.split('/').filter(x => x),
    channelName = pathParts[pathParts.length - 1],
    pool = await fetch(`/api/stats/${channelName}`).then(res => res.json());
    
  // update text on the page
  document.title = `${pool.name} statistics`;
  document.getElementById('pool-name').innerText = pool.name;
  document.getElementById('participant-count').innerText = pool.participant_count;
  document.getElementById('round-count').innerText = pool.round_count;
  document.getElementById('matches-count').innerText = pool.matches.length;
  document.getElementById('avg-round-size').innerText = Math.round((pool.matches.length * 2) / pool.round_count);
  document.getElementById('meetup-rate').innerText = `${Math.round((pool.matches.filter(match => match.met).length / pool.matches.length) * 100) || 'N/A'}%`;
  
  // populate the leaderboard
  const leaderboard = document.querySelector('#leaderboard tbody');
  pool.people = pool.people.map(person => Object.assign(person, {
      people_met: pool.matches.reduce((acc, cur) =>
        cur.met && (cur.person_1 === person.id || cur.person_2 === person.id) ? acc + 1 : acc, 0)
  }));
  let curRank = 1;
  pool.people
  .sort((a, b) => b.people_met - a.people_met)
  .forEach((person, index, people) => {
    const tr = document.createElement('tr');
    if (people[index-1] && people[index-1].people_met > person.people_met) {
      curRank++;
    }
    tr.innerHTML = `
      <td class="rank">${curRank}</td>
      <td class="name">${person.full_name}</td>
      <td class="people-met">${person.people_met}</td>
    `
    leaderboard.appendChild(tr);
  })

  // D3 simulation setup
  const links = pool.matches.map(match => ({
    source: match.person_1,
    target: match.person_2,
    met: match.met 
  })),
    nodes = pool.people;

  const simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(d => d.id))
    .force('charge', d3.forceManyBody().strength(10))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('collide', d3.forceCollide(d => boundingBox(d)));

  const svg = d3.select('figure').append('svg')
    .attr('viewBox', [0, 0, width, height]);

  const link = svg.append('g')
    .attr('class', 'links')
    .selectAll('line')
    .data(links)
    .join('line')
    .attr('class', d => 
      `person-${d.source.id} ${d.met ? 'met' : ''} person-${d.target.id}`
    );

  const node = svg.append('g')
    .attr('class', 'nodes')
    .selectAll('g')
    .data(nodes)
    .enter().append('g')
    .attr('class', d => {
      const matchedWith = pool.matches
      .filter(match => match.person_1 === d.id || match.person_2 === d.id)
      .map(match => match.person_1 === d.id ? `person-${match.person_2}` : `person-${match.person_1}`)
      .join(' ')
      return `person person-${d.id} ${matchedWith}`
    })
    .call(drag(simulation))
    .on('mouseover', mouseover)
    .on('mouseout', mouseout);

  node.append('circle')
    .attr('fill', 'gray')
    .attr('r', d => (d.people_met * 2.5) + 5);

  node.append('text')
    .text(d => d.full_name)
    .attr('text-anchor', 'middle')
    .attr('y', '0.35em');

  simulation.on('tick', () => {
    link
      .attr('x1', d => d.source.x)
      .attr('y1', d => d.source.y)
      .attr('x2', d => d.target.x)
      .attr('y2', d => d.target.y);
    node
      .attr('transform', d => `translate(${d.x},${d.y})`)
  });

  document.querySelector('figure').classList.add('appear');
  const loading = document.getElementById('loading');
  loading.classList.add('disappear');
  window.setTimeout(() => loading.style.display = 'none', 2500);
}


// UTILITY FUNCTIONS

// specifies the size of the node's collision bounds.
// derive from category name length for long names to prevent overlap
function boundingBox(d) {
  return Math.max(d.full_name.length * 3.4, d.people_met * 2.5);
}

function mouseover(d) {
  document.querySelectorAll(`.person-${d.id}`)
  .forEach(el => {
    el.classList.add('selected');
  });
  document.querySelector('figure').classList.add('node-selected');
}

function mouseout(d) {
  document.querySelector('figure').classList.remove('node-selected');
  document.querySelectorAll(`.person-${d.id}`)
  .forEach(el => {
    el.classList.remove('selected');
  });
}

function drag(simulation) {
  const dragstarted = d => {
    if (!d3.event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
  }
  
  const dragged = d => {
    d.fx = d3.event.x;
    d.fy = d3.event.y;
  }
  
  const dragended = d => {
    if (!d3.event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
  }
  
  return d3.drag()
    .on('start', dragstarted)
    .on('drag', dragged)
    .on('end', dragended);
}

main();