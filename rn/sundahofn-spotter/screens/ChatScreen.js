// Chat tab: Each send POSTs the typed text to the n8n webhook (CHAT_URL);
// the agent fetches live harbour data server-side (no client-side history needed).
import { useState } from 'react';
import {
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { CHAT_URL } from '../lib/api';
import { theme } from '../lib/theme';
import Loader from '../components/uiverse-loading';

export default function ChatScreen() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Aye Aye Captain! Any requests to bestow on?' },
  ]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);

  // 1. show user msg in chat  2. send to agent  3. show reply
  async function send() {
    const text = input.trim();
    if (text === '' || sending) return;
    const next = [...messages, { role: 'user', content: text }];
    setMessages(next);
    setInput('');
    setSending(true);
    try {
      const res = await fetch(CHAT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, user: 'rn-app' }),
      });
      const data = await res.json();
      setMessages([...next, { role: 'assistant', content: data.reply || '(no reply)' }]);
    } catch (e) {
      setMessages([...next, { role: 'assistant', content: 'Offline — could not reach the agent.' }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <KeyboardAvoidingView // push content up when ios keyboard pops
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      {/* FlatList stamps one chat bubble per message in the messages array */}
      <FlatList
        style={styles.list}
        contentContainerStyle={styles.listContent}
        data={messages}
        keyExtractor={(_, i) => String(i)} // hidden PK for each row — position in the array
        renderItem={({ item }) => (
          // bubble flips side + colour based on who sent it — user right, assistant left
          <View style={[styles.bubble, item.role === 'user' ? styles.userBubble : styles.assistantBubble]}>
            <Text style={item.role === 'user' ? styles.userText : styles.assistantText}>{item.content}</Text>
          </View>
        )}
        ListFooterComponent={
          // Msg waiting-loader gotten from uiverse while waiting for response
          sending ? (
            <View style={styles.loaderBubble}>
              <Loader />
            </View>
          ) : null
        }
      />

      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          placeholder="Ask about the harbour…"
          placeholderTextColor={theme.textMuted}
          value={input}
          onChangeText={setInput}
          onSubmitEditing={send}
          editable={!sending}
          returnKeyType="send"
        />
        <TouchableOpacity
          style={[styles.sendBtn, (sending || input.trim() === '') && styles.sendBtnDisabled]}
          onPress={send}
          disabled={sending || input.trim() === ''}
        >
          <Text style={styles.sendBtnText}>Send</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: theme.background },
  list: { flex: 1 },
  listContent: { padding: theme.space.md },
  bubble: { maxWidth: '80%', padding: theme.space.sm + 2, borderRadius: theme.radius.md, marginBottom: theme.space.sm },
  userBubble: { backgroundColor: theme.accent, alignSelf: 'flex-end' },
  assistantBubble: { backgroundColor: theme.surface, alignSelf: 'flex-start' },
  loaderBubble: {
    backgroundColor: theme.scrim,
    alignSelf: 'flex-start',
    paddingHorizontal: theme.space.md,
    paddingVertical: theme.space.sm,
    borderRadius: theme.radius.md,
    marginBottom: theme.space.sm,
  },
  userText: { color: '#fff', fontSize: theme.fontSize.body },
  assistantText: { color: theme.text, fontSize: theme.fontSize.body },
  inputRow: { flexDirection: 'row', padding: theme.space.sm, backgroundColor: theme.surface, borderTopWidth: 1, borderTopColor: theme.separator },
  input: {
    flex: 1,
    backgroundColor: theme.surfaceElevated,
    color: theme.text,
    borderWidth: 1,
    borderColor: theme.inputBorder,
    borderRadius: theme.radius.lg,
    paddingHorizontal: theme.space.md + 2,
    paddingVertical: theme.space.sm + 2,
    fontSize: theme.fontSize.body,
  },
  sendBtn: { marginLeft: theme.space.sm, paddingHorizontal: theme.space.lg, justifyContent: 'center', backgroundColor: theme.accent, borderRadius: theme.radius.lg },
  sendBtnDisabled: { backgroundColor: theme.accentMuted },
  sendBtnText: { color: '#fff', fontWeight: theme.weight.medium },
});
