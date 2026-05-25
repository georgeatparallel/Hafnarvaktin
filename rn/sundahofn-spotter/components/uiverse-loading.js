// Three bouncing dots — a uiverse.io loader redone with RN's Animated API
// (no extra deps). Used in the Chat tab while a reply is in flight.
import { useEffect, useRef } from 'react';
import { Animated, Easing, StyleSheet, View } from 'react-native';

const BOUNCE_MS = 500;
const DOT_DELAYS_MS = [0, 200, 300];

function Dot({ delay }) {
  const offset = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(offset, {
          toValue: 1,
          duration: BOUNCE_MS,
          delay,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
        Animated.timing(offset, {
          toValue: 0,
          duration: BOUNCE_MS,
          easing: Easing.inOut(Easing.ease),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [offset, delay]);

  const translateY = offset.interpolate({ inputRange: [0, 1], outputRange: [0, -9] });
  const shadowScale = offset.interpolate({ inputRange: [0, 1], outputRange: [1.5, 0.5] });
  const shadowOpacity = offset.interpolate({ inputRange: [0, 1], outputRange: [0.7, 0.3] });

  return (
    <View style={styles.column}>
      <Animated.View style={[styles.dot, { transform: [{ translateY }] }]} />
      <Animated.View
        style={[
          styles.shadow,
          { opacity: shadowOpacity, transform: [{ scaleX: shadowScale }] },
        ]}
      />
    </View>
  );
}

export default function Loader() {
  return (
    <View style={styles.wrapper}>
      {DOT_DELAYS_MS.map((delay, i) => (
        <Dot key={i} delay={delay} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'flex-end',
    height: 26,
    paddingHorizontal: 2,
  },
  column: {
    width: 14,
    alignItems: 'center',
    marginHorizontal: 3,
    height: 22,
    justifyContent: 'flex-end',
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
    backgroundColor: '#ffffff',
    marginBottom: 4,
  },
  shadow: {
    width: 7,
    height: 2,
    borderRadius: 3.5,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
});
