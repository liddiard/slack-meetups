(function() {
    function getMondays(d) {
        const mondays = [],
            month = d.getMonth();
        d.setDate(1);
    
        // Get the first Monday in the month
        while (d.getDay() !== 1) {
            d.setDate(d.getDate() + 1);
        }
    
        // Get all the other Mondays in the month
        while (d.getMonth() === month) {
            mondays.push(new Date(d.getTime()));
            d.setDate(d.getDate() + 7);
        }
    
        return mondays;
    }

    const date = new Date(),
        thisMonth = date.getMonth(),
        nextMonth = thisMonth + 1,
        mondaysThisMonth = getMondays(date);
    date.setMonth(nextMonth);
    const mondaysNextMonth = getMondays(date),
        matchingDays = [
            mondaysThisMonth[0], // first Monday of this month
            mondaysThisMonth[1], // second Monday of this month
            mondaysThisMonth[2], // third Monday of this month
            mondaysNextMonth[0] // first Monday of next month
        ],
        nextMatchingDate = matchingDays.find(day => day > new Date()),
        nextMatchingDateString = `Monday, ${nextMatchingDate.toLocaleString('en-us', { month: 'long' })} ${nextMatchingDate.getDate()}`;
    
    Array.from(document.querySelectorAll('.next-session')).forEach(el => 
        el.innerHTML = `The next round of pairing starts <time>${nextMatchingDateString}</time>!`);
})()
