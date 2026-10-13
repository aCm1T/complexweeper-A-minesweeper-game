"""Optional GStreamer audio. Missing audio plugins never block gameplay."""
from engine import ROOT


class Sound:
    def __init__(self, fake=False):
        self.players = {}
        self.error = None
        self.Gst = None
        self.decoded = set()
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst
            Gst.init(None)
            self.Gst = Gst
            for name in ['mine_1', 'mine_2', 'mine_3', 'mine_4', 'win', 'tick']:
                player = Gst.ElementFactory.make('playbin', None)
                if player is None:
                    raise RuntimeError('缺少 GStreamer playbin 插件')
                player.set_property('uri', (ROOT/'linux'/'sounds'/f'{name}.wav').as_uri())
                if fake:
                    player.set_property('audio-sink', Gst.ElementFactory.make('fakesink', None))
                bus = player.get_bus()
                bus.add_signal_watch()
                bus.connect('message', self._message, player, name)
                self.players[name] = player
        except (ImportError, ValueError, RuntimeError) as e:
            self.error = str(e)
            self.close()

    def _message(self, bus, msg, player, name):
        if msg.type == self.Gst.MessageType.ERROR:
            self.error = str(msg.parse_error()[0])
        if msg.type == self.Gst.MessageType.EOS:
            self.decoded.add(name)
        if msg.type in (self.Gst.MessageType.ERROR, self.Gst.MessageType.EOS):
            player.set_state(self.Gst.State.NULL)

    def play(self, name):
        if name in self.players:
            p = self.players[name]
            p.set_state(self.Gst.State.NULL)
            p.set_state(self.Gst.State.PLAYING)

    def close(self):
        for p in self.players.values():
            p.set_state(self.Gst.State.NULL)
        self.players.clear()
