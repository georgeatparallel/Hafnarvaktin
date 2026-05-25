// Email + password auth.
// on success, Firebase trips auth and flips login @App.js
import { useState } from 'react';
import { Alert, Button, StatusBar, StyleSheet, Text, TextInput, View } from 'react-native';
import { createUserWithEmailAndPassword, signInWithEmailAndPassword } from 'firebase/auth';
import { auth } from '../firebaseConfig';
import { theme } from '../lib/theme';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Sign into existing account
  async function handleLogin() {
    try {
      await signInWithEmailAndPassword(auth, email.trim(), password);
    } catch (e) {
      Alert.alert('Login failed', e.message);
    }
  }

  // Create new account
  async function handleSignUp() {
    try {
      await createUserWithEmailAndPassword(auth, email.trim(), password);
    } catch (e) {
      Alert.alert('Sign-up failed', e.message);
    }
  }

  return (
    <View style={styles.container}>
      <StatusBar barStyle="light-content" backgroundColor={theme.background} />
      <Text style={styles.title}>Sundahöfn Spotter</Text>
      <Text style={styles.subtitle}>Live harbour watch · Ísafjörður</Text>

      <TextInput
        style={styles.input}
        placeholder="Email"
        placeholderTextColor={theme.textMuted}
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        placeholderTextColor={theme.textMuted}
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      <View style={styles.row}>
        <Button title="Log in" onPress={handleLogin} color={theme.accent} />
        <Button title="Sign up" onPress={handleSignUp} color={theme.accent} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: 'center', padding: theme.space.xxl, backgroundColor: theme.background },
  title: { fontSize: theme.fontSize.hero, fontWeight: theme.weight.bold, textAlign: 'center', color: theme.text },
  subtitle: { fontSize: theme.fontSize.small, color: theme.textSecondary, textAlign: 'center', marginBottom: theme.space.xxl },
  input: {
    borderWidth: 1,
    borderColor: theme.separator,
    backgroundColor: theme.surface,
    color: theme.text,
    borderRadius: theme.radius.sm,
    padding: theme.space.md,
    marginBottom: theme.space.md,
    fontSize: theme.fontSize.label,
  },
  row: { flexDirection: 'row', justifyContent: 'space-around', marginTop: theme.space.sm },
});
