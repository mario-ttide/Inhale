// The geometry stage of a graphics program (NVN stage 2), between its vertex and fragment stages. vk_shader.cpp includes
// this inside its namespace, after Env, translate and profile_graphics, and calls it from translate_into and where a
// program's key is made (graphics_key). A file of this fork: upstream draws such a program without the stage.
//
// Kirby and the Forgotten Land has the stage in six mouthful forms' models (Ring, RingClock, RingGear, Elevator, Glider,
// DumpCar) and in the add-on's meteor decorations. The forms' adds each triangle's edge cross product to its three
// vertices' places in a storage buffer and passes the triangle on; the decorations' leaves out the triangles a
// per-vertex value marks. Drawn without it the forms' buffer stayed empty (issue #27). docs/design.md, section 9,
// "issue #27, mouthful forms drawn wrong: the geometry stage".
#pragma once

/// The geometry code this device runs: none without the geometryShader feature, and the program is then drawn as before
inline const Code* geometry_code(const Code* gs) {
    return gs && dev.features.geometryShader ? gs : nullptr;
}

/// A program's key with its geometry stage in it (none: the key as it is). kGeometryStage: add one when a change in this
/// file changes what such a program translates to, and the kept ones are made again: the file is not in the caches' stamp
/// (nx2/translator_files.py), which would make every program again
constexpr uint64_t kGeometryStage = 1;
inline uint64_t geometry_key(uint64_t key, const Code* gs) {
    return gs ? hash_bytes(&gs->key, sizeof gs->key, key + kGeometryStage) : key;
}

void dump_ir(const Program& p, const char* stage, const Shader::IR::Program& prog, uint64_t code_key);   // (vk_shader.cpp, further down)

struct GeometryStage {
    std::unique_ptr<Translation> t;
    Shader::RuntimeInfo rt{};
    int questions = 0;
    explicit operator bool() const { return t != nullptr; }
};

/// Translates the geometry code (none: an empty GeometryStage), and takes from the vertex stage's RuntimeInfo what the
/// last stage before the rasterizer does: the depth conversion and the noperspective outputs' scaling. The input is
/// triangles: the header does not say, and a draw of another primitive is left out (vk_draw.cpp build_graphics)
inline GeometryStage geometry_translate(const NvnState& s, const Code* gsc, const Shader::IR::Program& vs, Shader::RuntimeInfo& vrt) {
    GeometryStage g;
    if (!gsc) return g;
    Env env{s, *gsc, Shader::Stage::Geometry};
    g.t = translate(env, true);
    g.questions = env.texture_questions;
    g.rt.input_topology = Shader::InputTopology::Triangles;
    g.rt.previous_stage_stores = vs.info.stores;
    g.rt.convert_depth_mode = vrt.convert_depth_mode;
    g.rt.noperspective_outputs = vrt.noperspective_outputs;
    vrt.convert_depth_mode = false;
    vrt.noperspective_outputs.reset();
    return g;
}

/// Its SPIR-V and module as the program's next stage: after the vertex stage's and before the fragment stage's, since
/// one Bindings numbers the descriptors in the stages' order
inline void geometry_emit(GeometryStage& g, Program& p, const Code& gsc, Shader::Backend::Bindings& bindings,
                          std::vector<std::vector<uint32_t>>& kept) {
    const std::vector<uint32_t> spirv =
        Shader::Backend::SPIRV::EmitSPIRV(profile_graphics(VK_SHADER_STAGE_GEOMETRY_BIT), g.rt, g.t->program, bindings);
    dump_ir(p, "geometry", g.t->program, 0);
    Stage st;
    st.nvn_stage = 2;
    st.info = g.t->program.info;
    st.module = make_module(spirv);
    kept.push_back(spirv);
    st.vk_stage = VK_SHADER_STAGE_GEOMETRY_BIT;
    st.c1 = gsc.c1;
    p.stages.push_back(std::move(st));
}
