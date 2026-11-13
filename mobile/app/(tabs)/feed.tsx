// The swipe feed: one card at a time, ✕ or ♡. Every ♡ also lands in the
// wardrobe. The line at the top shows whether the feed is still best-sellers
// or already personalised to your likes.
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ProductCard } from "../../src/components/ProductCard";
import { progressLabel } from "../../src/feed/progress";
import { useFeed } from "../../src/feed/useFeed";
import { colors, styles } from "../../src/theme";

export default function Feed() {
  const feed = useFeed();
  const { card } = feed;

  let body;
  if (card) {
    body = (
      <ProductCard
        key={card.product.id}
        product={card.product}
        onLike={() => void feed.swipe("like")}
        onDislike={() => void feed.swipe("dislike")}
      />
    );
  } else if (feed.exhausted) {
    body = <Text style={styles.subtitle}>You've seen the whole catalogue. Start over from the Wardrobe tab.</Text>;
  } else if (feed.error) {
    body = (
      <Pressable style={styles.button} onPress={feed.retry}>
        <Text style={styles.buttonText}>Try again</Text>
      </Pressable>
    );
  } else {
    body = <ActivityIndicator size="large" />;
  }

  return (
    <SafeAreaView style={local.screen} edges={["top"]}>
      <Text style={local.progress}>{progressLabel(feed.progress)}</Text>
      {feed.error && <Text style={styles.error}>{feed.error}</Text>}
      <View style={local.body}>{body}</View>
    </SafeAreaView>
  );
}

const local = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background, paddingHorizontal: 16, paddingBottom: 16 },
  progress: { color: colors.muted, fontSize: 14, textAlign: "center", marginVertical: 8 },
  body: { flex: 1, alignItems: "center", justifyContent: "center" },
});
