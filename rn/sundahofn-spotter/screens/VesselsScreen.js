// Fleet tab: vessels currently in port and at sea at Sundahöfn.
import { useEffect, useState } from 'react';
import { Linking, RefreshControl, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { BACKEND_URL } from '../lib/api';
import { theme } from '../lib/theme';

export default function VesselsScreen() {
  const [vessels, setVessels] = useState(null);
  const [loading, setLoading] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/vessels/status`);
      const json = await res.json();
      setVessels(json);
    } catch {
      // keep whatever is shown - don't wipe list
    } finally {
      setLoading(false); // spinner off
    }
  }

  useEffect(() => {
    load(); // [] = run once on mount, not on every re-render
  }, []);

  const inPort = vessels?.inPort ?? []; // null until fetch completes — ?? [] prevents map() crashing
  const atSea = vessels?.atSea ?? [];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={theme.textSecondary} />}
    >
      <Text style={styles.sectionHeader}>In port ({inPort.length})</Text>
      {inPort.map((v) => (
        <VesselRow key={v.registrationNo ?? v.mmsi ?? v.name} vessel={v} />
      ))}

      <Text style={styles.sectionHeader}>At sea ({atSea.length})</Text>
      {atSea.map((v) => (
        <VesselRow key={v.registrationNo ?? v.mmsi ?? v.name} vessel={v} />
      ))}

      {!vessels && !loading && (
        <Text style={styles.empty}>No vessels found.</Text>
      )}
    </ScrollView>
  );
}

function VesselRow({ vessel }) {
  return (
    <View style={styles.row}>
      <Text style={styles.name}>{vessel.name}</Text>
      {vessel.registrationNo && (
        <Text style={styles.regno}>IS-{vessel.registrationNo}</Text>
      )}
      {vessel.speedKn >= 0.5 && (
        <Text style={styles.speed}>{vessel.speedKn.toFixed(1)} kn</Text>
      )}
      {vessel.registrationNo && (
        <TouchableOpacity onPress={() => Linking.openURL(`https://www.mbl.is/200milur/skipaskra/skip/${vessel.registrationNo}/`)}>
          <Text style={styles.mblLink}>mbl.is skipaskrá ↗</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.background },
  content: { padding: theme.space.md },
  sectionHeader: {
    fontSize: theme.fontSize.label,
    fontWeight: theme.weight.bold,
    color: theme.text,
    marginTop: theme.space.lg,
    marginBottom: theme.space.sm,
  },
  row: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius.md,
    padding: theme.space.lg - 2,
    marginBottom: theme.space.sm,
  },
  name: { fontSize: theme.fontSize.label, fontWeight: theme.weight.medium, color: theme.text },
  regno: { fontSize: theme.fontSize.small, color: theme.textSecondary, marginTop: theme.space.xs },
  speed: { fontSize: theme.fontSize.small, color: theme.textSecondary, marginTop: theme.space.xs },
  mblLink: { fontSize: theme.fontSize.small, color: theme.accent, marginTop: theme.space.sm },
  empty: { textAlign: 'center', color: theme.textSecondary, marginTop: 60 },
});
