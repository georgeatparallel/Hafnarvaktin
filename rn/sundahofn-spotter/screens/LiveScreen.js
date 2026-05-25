// Harbour tab: both Sundahöfn camera-snapshots (annotated server-side by
// YOLOv11m), re-fetched every 1.5s via a cache-buster query param.
import { useEffect, useState } from 'react';
import { Image, Linking, ScrollView, StyleSheet, Text, View } from 'react-native';
import { BACKEND_URL } from '../lib/api';
import { theme } from '../lib/theme';

const CAMERAS = [
  { id: 9, name: 'Sundahöfn N' },
  { id: 6, name: 'Sundahöfn S' },
];
const REFRESH_MS = 1500;

// build hyperlinks function for in-browser experience
function Link({ url, children }) {
  return (
    <Text style={styles.link} onPress={() => Linking.openURL(url)}>
      {children}
    </Text>
  );
}

export default function LiveScreen() {
  const [ts, setTs] = useState(Date.now());

  // Bump the timestamp on an interval so each <Image> URL is "new" and reloads.
  useEffect(() => {
    const id = setInterval(() => setTs(Date.now()), REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {CAMERAS.map((cam) => (
        <View key={cam.id} style={styles.card}>
          <Text style={styles.label}>{cam.name}</Text>
          <Image
            style={styles.image}
            source={{ uri: `${BACKEND_URL}/api/v1/cameras/${cam.id}/snapshot?t=${ts}` }}
            resizeMode="cover"
          />
        </View>
      ))}
      <Text style={styles.hint}>
        Updates every {REFRESH_MS / 1000}s · livestream provided by{' '}
        <Link url="https://www.sjoferdir.is/">sjoferdir.is</Link> and{' '}
        <Link url="https://www.snerpa.is/">snerpa.is</Link>
      </Text>
      <Text style={styles.hintMuted}>Detection boxes drawn by YOLOv11m on server.</Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.background },
  content: { padding: theme.space.md },
  card: { backgroundColor: theme.surface, borderRadius: theme.radius.md, overflow: 'hidden', marginBottom: theme.space.md },
  label: { fontSize: theme.fontSize.label, fontWeight: theme.weight.medium, padding: theme.space.sm + 2, color: theme.text },
  image: { width: '100%', aspectRatio: 16 / 9, backgroundColor: '#000' },
  hint: { textAlign: 'center', color: theme.textSecondary, fontSize: theme.fontSize.caption + 1, marginTop: theme.space.xs },
  hintMuted: { textAlign: 'center', color: theme.textMuted, fontSize: theme.fontSize.caption, marginTop: theme.space.xs, marginBottom: theme.space.md },
  link: { color: theme.accent },
});
