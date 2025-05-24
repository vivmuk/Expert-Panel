/**
 * Import function triggers from their respective submodules:
 *
 * const {onCall} = require("firebase-functions/v2/https");
 * const {onDocumentWritten} = require("firebase-functions/v2/firestore");
 *
 * See a full list of supported triggers at https://firebase.google.com/docs/functions
 */

const functions = require("firebase-functions");
const admin = require("firebase-admin");
const logger = require("firebase-functions/logger");

// Initialize Firebase Admin SDK
admin.initializeApp();

// Get a reference to the Firestore database
const db = admin.firestore();

// Import CORS middleware
// Make sure to install cors by running: npm install cors --save (or yarn add cors) in the functions directory
const cors = require("cors")({origin: true}); // Allow all origins for now, can be restricted later

/**
 * HTTP Cloud Function to save a user's report.
 * - Expects a POST request with a JSON body containing the report data.
 * - Authenticates the user using their ID token.
 * - Saves the report to Firestore under /users/{uid}/reports/{reportId}.
 */
exports.saveReport = functions.https.onRequest((request, response) => {
  // Handle CORS preflight requests and then the actual request
  cors(request, response, async () => {
    logger.info("saveReport function invoked.", {method: request.method});

    if (request.method !== "POST") {
      logger.warn("Invalid request method:", {method: request.method});
      return response.status(405).send("Method Not Allowed");
    }

    // 1. Authentication
    const idToken = request.headers.authorization?.split("Bearer ")[1];
    if (!idToken) {
      logger.warn("Authentication token not provided.");
      return response.status(403).send("Unauthorized: No token provided.");
    }

    let decodedToken;
    try {
      decodedToken = await admin.auth().verifyIdToken(idToken);
      logger.info("User authenticated:", {uid: decodedToken.uid});
    } catch (error) {
      logger.error("Error verifying auth token:", {error: error.message});
      return response.status(403).send("Unauthorized: Invalid token.");
    }

    const uid = decodedToken.uid;

    // 2. Get Report Data from Request Body
    const reportData = request.body.report; // Assuming the report is sent under a 'report' key
    if (!reportData || typeof reportData !== 'object' || Object.keys(reportData).length === 0) {
      logger.warn("Report data not provided or invalid in request body.", {uid: uid, body: request.body});
      return response.status(400).send("Bad Request: Report data must be a non-empty object.");
    }

    logger.info("Received report data for user:", {uid: uid, dataKeys: Object.keys(reportData)});

    // 3. Save to Firestore
    try {
      const userReportsRef = db.collection("users").doc(uid).collection("reports");
      const newReportRef = await userReportsRef.add({
        ...reportData, // Spread the received report data
        createdAt: admin.firestore.FieldValue.serverTimestamp(), // Add a server-side timestamp
        userId: uid // Store userId for potential denormalized queries if needed later
      });

      logger.info("Report successfully saved to Firestore for user:", {uid: uid, reportId: newReportRef.id});

      // Respond with success
      return response.status(200).json({
        message: "Report successfully saved to Firestore.",
        userId: uid,
        reportId: newReportRef.id
      });

    } catch (error) {
      logger.error("Error saving report to Firestore:", {uid: uid, error: error.message, stack: error.stack });
      return response.status(500).send("Internal Server Error: Could not save report.");
    }
  });
});

/**
 * HTTP Cloud Function to fetch a user's saved reports.
 * - Expects a GET request.
 * - Authenticates the user using their ID token.
 * - Fetches reports from Firestore under /users/{uid}/reports/.
 * - Orders reports by creation date (newest first).
 */
exports.getReports = functions.https.onRequest((request, response) => {
  cors(request, response, async () => {
    logger.info("getReports function invoked.", {method: request.method});

    if (request.method !== "GET") {
      logger.warn("Invalid request method for getReports:", {method: request.method});
      return response.status(405).send("Method Not Allowed");
    }

    // 1. Authentication
    const idToken = request.headers.authorization?.split("Bearer ")[1];
    if (!idToken) {
      logger.warn("Authentication token not provided for getReports.");
      return response.status(403).send("Unauthorized: No token provided.");
    }

    let decodedToken;
    try {
      decodedToken = await admin.auth().verifyIdToken(idToken);
      logger.info("User authenticated for getReports:", {uid: decodedToken.uid});
    } catch (error) {
      logger.error("Error verifying auth token for getReports:", {error: error.message});
      return response.status(403).send("Unauthorized: Invalid token.");
    }

    const uid = decodedToken.uid;

    // 2. Fetch Reports from Firestore
    try {
      const reportsSnapshot = await db.collection("users").doc(uid).collection("reports")
        .orderBy("createdAt", "desc") // Order by newest first
        .get();

      if (reportsSnapshot.empty) {
        logger.info("No reports found for user:", {uid: uid});
        return response.status(200).json([]); // Return empty array if no reports
      }

      const reports = [];
      reportsSnapshot.forEach((doc) => {
        reports.push({reportId: doc.id, ...doc.data()});
      });

      logger.info(`Fetched ${reports.length} reports for user:`, {uid: uid});
      return response.status(200).json(reports);

    } catch (error) {
      logger.error("Error fetching reports from Firestore:", {uid: uid, error: error.message, stack: error.stack });
      return response.status(500).send("Internal Server Error: Could not fetch reports.");
    }
  });
});

// Example of another function (can be removed if not needed)
// exports.anotherFunction = functions.https.onRequest((request, response) => {
//   cors(request, response, () => {
//     logger.info("anotherFunction invoked.");
//     response.send("Hello from another function!");
//   });
// });

// TODO: Add functions for fetching reports.
// TODO: Add Stripe integration functions.
