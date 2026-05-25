import { initializeApp } from 'firebase/app';
import { initializeAuth, getReactNativePersistence } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';
import AsyncStorage from '@react-native-async-storage/async-storage';

const firebaseConfig = {
  apiKey: 'AIzaSyAV5LaK9SImciBGWHZptA9aa69SRGCwGVU',
  authDomain: 'hafnarvaktin.firebaseapp.com',
  projectId: 'hafnarvaktin',
  storageBucket: 'hafnarvaktin.firebasestorage.app',
  messagingSenderId: '919047399015',
  appId: '1:919047399015:web:eefe378261439d9fc956c2',
  measurementId: 'G-PZNG8E2C19',
};

const app = initializeApp(firebaseConfig);

// Persist the login across app restarts via AsyncStorage so the user doesn't
// have to log in every time the app starts.
export const auth = initializeAuth(app, {
  persistence: getReactNativePersistence(AsyncStorage),
});

export const db = getFirestore(app);
export const storage = getStorage(app);
