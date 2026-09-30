
"""
Генерация шейдеров процедурно — кодом.
"""

class ShaderGenerator:
    @staticmethod
    def generate_anomaly_shader(anomaly_type):
        # GLSL шейдеры для аномалий
        if anomaly_type == "electra":
            vertex = """
            #version 130
            in vec4 p3d_Vertex;
            in vec3 p3d_Normal;
            uniform mat4 p3d_ModelViewProjectionMatrix;
            out vec3 normal;
            out vec3 pos;
            void main() {
                gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
                normal = p3d_Normal;
                pos = p3d_Vertex.xyz;
            }
            """
            fragment = """
            #version 130
            in vec3 normal;
            in vec3 pos;
            uniform float time;
            out vec4 fragColor;
            void main() {
                float flicker = sin(time*20.0 + pos.x*10.0)*0.5+0.5;
                vec3 color = vec3(0.2, 0.5, 1.0) * flicker;
                float glow = pow(1.0 - dot(normal, vec3(0,0,1)), 2.0);
                fragColor = vec4(color + glow, 0.7);
            }
            """
        elif anomaly_type == "zharka":
            vertex = """
            #version 130
            in vec4 p3d_Vertex;
            uniform mat4 p3d_ModelViewProjectionMatrix;
            out vec3 pos;
            void main() {
                gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
                pos = p3d_Vertex.xyz;
            }
            """
            fragment = """
            #version 130
            in vec3 pos;
            uniform float time;
            out vec4 fragColor;
            void main() {
                float heat = sin(time*5.0 + length(pos)*2.0)*0.5+0.5;
                vec3 color = mix(vec3(1.0,0.3,0.0), vec3(1.0,0.8,0.0), heat);
                fragColor = vec4(color, 0.6);
            }
            """
        else:
            vertex = """
            #version 130
            in vec4 p3d_Vertex;
            uniform mat4 p3d_ModelViewProjectionMatrix;
            void main() { gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex; }
            """
            fragment = """
            #version 130
            uniform float time;
            out vec4 fragColor;
            void main() {
                float pulse = sin(time*3.0)*0.5+0.5;
                fragColor = vec4(0.5, pulse, 0.2, 0.6);
            }
            """
        return vertex, fragment

    @staticmethod
    def generate_terrain_shader():
        vertex = """
        #version 130
        in vec4 p3d_Vertex;
        in vec3 p3d_Normal;
        in vec2 p3d_MultiTexCoord0;
        uniform mat4 p3d_ModelViewProjectionMatrix;
        uniform mat4 p3d_ModelMatrix;
        out vec3 worldNormal;
        out vec2 texCoord;
        out vec3 worldPos;
        void main() {
            gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
            worldNormal = mat3(p3d_ModelMatrix) * p3d_Normal;
            texCoord = p3d_MultiTexCoord0;
            worldPos = (p3d_ModelMatrix * p3d_Vertex).xyz;
        }
        """
        fragment = """
        #version 130
        in vec3 worldNormal;
        in vec2 texCoord;
        in vec3 worldPos;
        uniform vec3 sunDir;
        uniform vec3 sunColor;
        out vec4 fragColor;
        void main() {
            vec3 normal = normalize(worldNormal);
            float diff = max(dot(normal, -sunDir), 0.0);
            vec3 baseColor = vec3(0.3, 0.5, 0.2);
            // биомы по высоте
            if (worldPos.y < 5.0) baseColor = vec3(0.2, 0.4, 0.6);
            else if (worldPos.y > 30.0) baseColor = vec3(0.5, 0.5, 0.5);
            vec3 color = baseColor * (0.3 + diff*0.7) * sunColor;
            fragColor = vec4(color, 1.0);
        }
        """
        return vertex, fragment

    @staticmethod
    def generate_water_shader():
        vertex = """
        #version 130
        in vec4 p3d_Vertex;
        uniform mat4 p3d_ModelViewProjectionMatrix;
        uniform float time;
        out vec2 texCoord;
        void main() {
            vec4 pos = p3d_Vertex;
            pos.y += sin(time + pos.x*0.1)*0.2;
            gl_Position = p3d_ModelViewProjectionMatrix * pos;
            texCoord = p3d_Vertex.xz * 0.1;
        }
        """
        fragment = """
        #version 130
        in vec2 texCoord;
        uniform float time;
        out vec4 fragColor;
        void main() {
            float wave = sin(texCoord.x*10.0 + time)*0.1 + sin(texCoord.y*10.0 + time*1.2)*0.1;
            vec3 color = vec3(0.1, 0.4, 0.6) + wave;
            fragColor = vec4(color, 0.8);
        }
        """
        return vertex, fragment
