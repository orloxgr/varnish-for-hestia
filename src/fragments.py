"""Parse the supported site-local VCL language; never splice arbitrary VCL."""
import re


class FragmentError(ValueError):
    pass


TOKEN = re.compile(r'''(?P<space>\s+)|(?P<comment>\#[^\n]*|//[^\n]*)|
    (?P<string>"(?:[^"\\\r\n]|\\[^\r\n])*")|
    (?P<duration>\d+(?:\.\d+)?(?:ms|s|m|h|d|w)\b)|
    (?P<number>\d+(?:\.\d+)?)|(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)|
    (?P<operator>==|!=|!~|<=|>=|&&|\|\||[{}();,=~!<>+])''', re.X)


class Parser:
    def __init__(self, source, stage):
        if stage not in ('recv', 'backend_response'):
            raise FragmentError('Unknown VCL editing section')
        if not isinstance(source, str) or len(source.encode()) > 16384:
            raise FragmentError('A VCL section may contain at most 16 KiB')
        self.tokens = []
        self.stage = stage
        position = 0
        while position < len(source):
            match = TOKEN.match(source, position)
            if not match:
                raise FragmentError('Unsupported VCL character or literal')
            if match.lastgroup not in ('space', 'comment'):
                self.tokens.append((match.lastgroup, match.group()))
            position = match.end()
        if len(self.tokens) > 4096:
            raise FragmentError('Too many VCL tokens')
        self.index = 0

    def peek(self):
        return self.tokens[self.index][1] if self.index < len(self.tokens) else None

    def take(self, expected=None):
        if self.peek() is None or (expected is not None and self.peek() != expected):
            raise FragmentError('Invalid VCL syntax')
        token = self.tokens[self.index]
        self.index += 1
        return token

    def block(self, depth=0, nested=False):
        if depth > 16:
            raise FragmentError('VCL condition nesting is too deep')
        while self.peek() is not None and self.peek() != '}':
            word = self.take()[1]
            if word == 'if':
                self.take('('); self.expression(); self.take(')')
                self.take('{'); self.block(depth + 1, True); self.take('}')
                if self.peek() == 'else':
                    self.take('else')
                    if self.peek() == 'if':
                        # Parse else-if through the same statement grammar.
                        self.block_one_if(depth)
                    else:
                        self.take('{'); self.block(depth + 1, True); self.take('}')
            elif word in ('set', 'unset'):
                target = self.take()[1]
                if not self.writable(target):
                    raise FragmentError('This field is outside the site-local editing scope')
                if word == 'set':
                    self.take('='); self.expression()
                elif not '.http.' in target:
                    raise FragmentError('Only custom headers can be unset')
                self.take(';')
            elif word == 'return' and self.stage == 'recv':
                self.take('('); self.take('pass'); self.take(')'); self.take(';')
            else:
                raise FragmentError('Unsupported VCL statement')
        if not nested and self.peek() is not None:
            raise FragmentError('A VCL section cannot close its containing scope')

    def block_one_if(self, depth):
        self.take('if'); self.take('('); self.expression(); self.take(')')
        self.take('{'); self.block(depth + 1, True); self.take('}')
        if self.peek() == 'else':
            self.take('else')
            if self.peek() == 'if':
                self.block_one_if(depth + 1)
            else:
                self.take('{'); self.block(depth + 1, True); self.take('}')

    def writable(self, name):
        prefix = 'req' if self.stage == 'recv' else 'beresp'
        if re.fullmatch(prefix + r'\.http\.X-User-[A-Za-z0-9_-]{1,80}', name, re.I):
            return True
        return self.stage == 'backend_response' and name in ('beresp.ttl', 'beresp.grace', 'beresp.keep')

    def readable(self, name):
        request = 'req' if self.stage == 'recv' else 'bereq'
        if name in (request + '.url', request + '.method'):
            return True
        match = re.fullmatch(request + r'\.http\.([A-Za-z0-9_-]{1,100})', name)
        if match and not match[1].lower().startswith(('x-hvh-', 'x-esi-', 'x-ultracache-')):
            return True
        if self.stage == 'backend_response':
            return name in ('beresp.status', 'beresp.ttl', 'beresp.grace', 'beresp.keep',
                            'beresp.http.Content-Type', 'beresp.http.Cache-Control')
        return False

    def expression(self, level=0):
        if level > 24:
            raise FragmentError('VCL expression nesting is too deep')
        self.atom(level)
        while self.peek() in ('==', '!=', '~', '!~', '<', '>', '<=', '>=', '&&', '||', '+'):
            self.take(); self.atom(level)

    def atom(self, level):
        if level > 24:
            raise FragmentError('VCL expression nesting is too deep')
        kind, value = self.take()
        if value == '!':
            self.atom(level + 1)
        elif value == '(':
            self.expression(level + 1); self.take(')')
        elif kind in ('string', 'duration', 'number') or value in ('true', 'false'):
            pass
        elif value in ('regsub', 'regsuball'):
            self.take('('); self.expression(level + 1)
            self.take(','); self.expression(level + 1)
            self.take(','); self.expression(level + 1); self.take(')')
        elif not self.readable(value):
            raise FragmentError('Unsupported VCL expression or field')


def validate(source, stage):
    parser = Parser(source, stage)
    parser.block()
    # Re-render only parsed tokens. Comments and unrecognized syntax never reach
    # the native compiler, while Varnish remains the authority on types/regexes.
    return ' '.join(value for _, value in parser.tokens)
