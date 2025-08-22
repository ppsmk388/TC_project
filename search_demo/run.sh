

# 启动（前台输出 + 写入 PID 文件）
python /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/host_vllm.py \
  --model /home/v-huzhengyu/zhengyu_blob_home/hugging_face_models/models--Qwen--Qwen3-8B/snapshots/2069b3fae1114555f3c020c81410e51fa0f656f2 \
  --model-name Qwen3-8B \
  --port 8000 \
  --gpu 1 \
  --pid-file /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/vllm_8000.json



# 关闭

python /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/stop_vllm.py \
  --pid-file /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/vllm_8000.json
# # 或者
# python stop_vllm.py --port 8000




# 调用

python /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/demo_call.py  \
  --port 8000   \
  --model-name Qwen3-8B \
  --question "给一个简短且专业的 vLLM 介绍。"








# 启动示例（接 AG2 DeepResearch 用 Qwen3）
python /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/host_vllm_update_qwen3.py \
  --model /home/v-huzhengyu/zhengyu_blob_home/hugging_face_models/models--Qwen--Qwen3-8B/snapshots/2069b3fae1114555f3c020c81410e51fa0f656f2 \
  --model-name Qwen3-8B \
  --port 8000 \
  --gpu 1 \
  --pid-file /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/vllm_8000.json \
  --enable-auto-tool-choice \
  --tool-call-parser hermes





# 启动示例（接 AG2 DeepResearch 用 Qwen3）
python /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/host_vllm_update_qwen3.py \
  --model /home/v-huzhengyu/zhengyu_blob_home/hugging_face_models/models--Qwen--Qwen3-32B/snapshots/30b8421510892303dc5ddd6cd0ac90ca2053478d \
  --model-name Qwen3-8B \
  --port 8000 \
  --gpu 4 \
  --pid-file /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/vllm_8000.json \
  --enable-auto-tool-choice \
  --tool-call-parser hermes

# 启动示例（接 AG2 DeepResearch 用 Qwen3）
python /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/host_vllm_update_qwen3.py \
  --model /home/v-huzhengyu/zhengyu_blob_home/hugging_face_models/models--Qwen--Qwen2.5-VL-7B-Instruct/snapshots/cc594898137f460bfe9f0759e9844b3ce807cfb5 \
  --model-name Qwen3-8B \
  --port 8000 \
  --gpu 1 \
  --pid-file /home/v-huzhengyu/zhengyu_blob_home/z_p_folder/0807_HR_agent/local_vllm/vllm_8000.json \
  --enable-auto-tool-choice \
  --tool-call-parser hermes




