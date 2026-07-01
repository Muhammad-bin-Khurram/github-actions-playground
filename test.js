const { add, subtract } = require('./math');

function assertEqual(actual, expected, testName) {
  if (actual === expected) {
    console.log(`✅ PASS: ${testName}`);
  } else {
    console.log(`❌ FAIL: ${testName} (expected ${expected}, got ${actual})`);
    process.exit(1); // ye exit code 1 dega taake CI ko pata chale test fail hua
  }
}

assertEqual(add(2, 3), 5, "add(2,3) should be 5");
assertEqual(subtract(5, 2), 3, "subtract(5,2) should be 3");

console.log("All tests passed!");