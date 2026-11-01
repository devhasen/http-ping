"use strict";
const url = process.argv[2];
const count = Number(process.argv[3]) || 5;
if (!url) {
    console.log('usage: httpping <url> [count]');
    process.exit(1);
}
async function ping() {
    const t = Date.now();
    const res = await fetch(url);
    await res.text();
    return Date.now() - t;
}
(async () => {
    const times = [];
    for (let i = 0; i < count; i++) {
        try {
            const ms = await ping();
            times.push(ms);
            console.log(i + 1, ms + 'ms');
        }
        catch (e) {
            console.log(i + 1, 'error');
        }
    }
    if (times.length) {
        const avg = Math.round(times.reduce((a, b) => a + b, 0) / times.length);
        console.log('min', Math.min(...times), 'max', Math.max(...times), 'avg', avg);
    }
})();
