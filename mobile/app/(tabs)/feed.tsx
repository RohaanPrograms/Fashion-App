// The swipe feed: one card at a time, ✕ or ♡. Every ♡ also lands in the
// wardrobe. At the top: the filter buttons, then a line saying whether the
// feed is still best-sellers or already personalised to your likes.
import { useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FilterBar } from "../../src/components/FilterBar";
import { ProductCard } from "../../src/components/ProductCard";
import { WhyPanel } from "../../src/components/WhyPanel";
import { exhaustedMessage } from "../../src/feed/filters";
import { progressLabel } from "../../src/feed/progress";
import { useFeed } from "../../src/feed/useFeed";
import { colors, styles } from "../../src/theme";

export default function Feed() {
  const feed = useFeed();
  const { card } = feed;
  const [whyOpen, setWhyOpen] = useState(false);

  function swipe(type: "like" | "dislike") {
    setWhyOpen(false); // the next card starts with the panel closed
    void feed.swipe(type);
  }

  let body;
  if (card) {
    body = (
      <ProductCard
        key={card.product.id}
        product={card.product}
        onLike={() => swipe("like")}
        onDislike={() => swipe("dislike")}
        onToggleWhy={() => setWhyOpen((open) => !open)}
        whyOpen={whyOpen}
      >
        <WhyPanel product={card.product} reason={card.reason} likesNeeded={feed.progress?.likesNeeded ?? 0} />
      </ProductCard>
    );
  } else if (feed.exhausted) {
    body = <Text style={styles.subtitle}>{exhaustedMessage(feed.filter, feed.options)}</Text>;
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
      <FilterBar
        options={feed.options}
        picks={feed.filter}
        onChange={(picks) => {
          setWhyOpen(false); // new cards are coming; start them closed
          feed.setFilter(picks);
        }}
      />
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
