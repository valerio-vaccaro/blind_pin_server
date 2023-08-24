import time
import json
import os
from flask import Flask, request, jsonify
from .server import PINServerECDH, PINServerECDHv2
from .pindb import PINDb
from wallycore import hex_from_bytes, hex_to_bytes, AES_KEY_LEN_256, \
    AES_BLOCK_LEN
from dotenv import load_dotenv

b2h = hex_from_bytes
h2b = hex_to_bytes

# Time we will retain active sessions, in seconds.
# ie. maximum time allowed 'start_handshake' (which creates the session)
# and the get-/set-pin call, which utilises it.
# Can be set in environment, defaults to 5mins
load_dotenv()
SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME', 300))


def flask_server():
    # Load, verify, and cache server static key at startup
    # (Refuse to start if key non-existing or invalid)
    PINServerECDH.load_private_key()

    sessions = {}
    app = Flask(__name__)

    def _cleanup_expired_sessions():
        nonlocal sessions
        time_now = int(time.time())
        sessions = dict(filter(
            lambda s: time_now - s[1].time_started < SESSION_LIFETIME,
            sessions.items()))

    @app.route('/', methods=['GET'])
    def alive():
        return ""

    @app.route('/start_handshake', methods=['POST'])
    def start_handshake_route():
        app.logger.debug('Number of sessions {}'.format(len(sessions)))

        # Create a new ephemeral server/session and get its signed pubkey
        e_ecdh_server = PINServerECDH()
        pubkey, sig = e_ecdh_server.get_signed_public_key()
        ske = b2h(pubkey)

        # Cache new session
        _cleanup_expired_sessions()
        sessions[ske] = e_ecdh_server

        # Return response
        return jsonify({'ske': ske,
                        'sig': b2h(sig)})

    def _complete_server_call_v1(pin_func, udata):
        ske = udata['ske']
        assert 'replay_counter' not in udata

        # Get associated session (ensuring not stale)
        _cleanup_expired_sessions()
        e_ecdh_server = sessions[ske]

        # get/set pin and get response data
        encrypted_key, hmac = e_ecdh_server.call_with_payload(
                h2b(udata['cke']),
                h2b(udata['encrypted_data']),
                h2b(udata['hmac_encrypted_data']),
                pin_func)

        # Expecting to return an encrypted aes-key
        assert len(encrypted_key) == AES_KEY_LEN_256 + (2*AES_BLOCK_LEN)

        # Cleanup session
        del sessions[ske]
        _cleanup_expired_sessions()

        # Return response
        return jsonify({'encrypted_key': b2h(encrypted_key),
                        'hmac': b2h(hmac)})

    def _complete_server_call_v2(pin_func, udata):
        assert 'ske' not in udata
        assert len(udata['replay_counter']) == 8
        cke = h2b(udata['cke'])
        replay_counter = h2b(udata['replay_counter'])
        e_ecdh_server = PINServerECDHv2(replay_counter, cke)
        encrypted_key, hmac = e_ecdh_server.call_with_payload(
                cke,
                h2b(udata['encrypted_data']),
                h2b(udata['hmac_encrypted_data']),
                pin_func)

        # Expecting to return an encrypted aes-key
        assert len(encrypted_key) == AES_KEY_LEN_256 + (2*AES_BLOCK_LEN)

        # Return response
        return jsonify({'encrypted_key': b2h(encrypted_key),
                        'hmac': b2h(hmac)})

    def _complete_server_call(pin_func):
        try:
            # Get request data
            udata = json.loads(request.data)
            if 'replay_counter' in udata:
                return _complete_server_call_v2(pin_func, udata)
            return _complete_server_call_v1(pin_func, udata)

        except Exception as e:
            app.logger.error("Error: {} {}".format(type(e), e))
            app.logger.error("Request body: {}".format(request.data))
            raise e

    @app.route('/get_pin', methods=['POST'])
    def get_pin_route():
        return _complete_server_call(PINDb.get_aes_key)

    @app.route('/set_pin', methods=['POST'])
    def set_pin_route():
        return _complete_server_call(PINDb.set_pin)

    return app


app = flask_server()
