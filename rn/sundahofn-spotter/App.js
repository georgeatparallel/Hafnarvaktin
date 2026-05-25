// shows LoginScreen when signed out, otherwise the bottom-tab
// navigator (Harbour / Fleet / Chat).
import { useEffect, useState } from 'react';
import { DarkTheme, NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { onAuthStateChanged, signOut } from 'firebase/auth';
import { Image, StatusBar, StyleSheet, Text } from 'react-native';

import { auth } from './firebaseConfig';
import { theme } from './lib/theme';
import LoginScreen from './screens/LoginScreen';
import LiveScreen from './screens/LiveScreen';
import VesselsScreen from './screens/VesselsScreen';
import ChatScreen from './screens/ChatScreen';

// Tab-bar icons
const ICONS = {
  Harbour: require('./components/icons/harbour.png'),
  Fleet: require('./components/icons/fleet.png'),
  Chat: require('./components/icons/chat.png'),
};

const Tab = createBottomTabNavigator();

const navTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    background: theme.background,
    card: theme.surface,
    text: theme.text,
    border: theme.separator,
    primary: theme.accent,
  },
};

// Header-right action: sign out, which trips the auth listener below.
function LogoutLink() {
  return (
    <Text onPress={() => signOut(auth)} style={styles.logout}>
      Log out
    </Text>
  );
}

// Tab-bar icons
function TabIcon({ name, focused }) {
  return (
    <Image
      source={ICONS[name]}
      resizeMode="contain"
      style={[styles.tabIcon, { opacity: focused ? 1 : 0.4 }]}
    />
  );
}

export default function App() {
  const [userId, setUserId] = useState(null);

  // Track Firebase auth; null userId → show the login screen.
  useEffect(() => onAuthStateChanged(auth, (user) => setUserId(user ? user.uid : null)), []);

  if (!userId) return <LoginScreen />;

  return (
    <NavigationContainer theme={navTheme}>
      <StatusBar barStyle="light-content" backgroundColor={theme.background} />
      <Tab.Navigator
        screenOptions={({ route }) => ({
          headerRight: () => <LogoutLink />,
          tabBarActiveTintColor: theme.accent,
          tabBarInactiveTintColor: theme.textSecondary,
          tabBarIcon: ({ focused }) => <TabIcon name={route.name} focused={focused} />,
        })}
      >
        <Tab.Screen name="Harbour" component={LiveScreen} />
        <Tab.Screen name="Fleet" component={VesselsScreen} />
        <Tab.Screen name="Chat" component={ChatScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  logout: { color: theme.accent, fontSize: theme.fontSize.label, marginRight: theme.space.md },
  tabIcon: { width: 24, height: 24, tintColor: theme.text },
});
