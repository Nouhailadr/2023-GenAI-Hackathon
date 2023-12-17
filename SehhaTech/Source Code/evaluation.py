from datasets import load_dataset
benchmark_dataset = load_dataset("flaviagiammarino/vqa-rad", split="test")


import gradio as gr
import numpy as np
import pandas as pd
from PIL import Image

from vlm_model import *
import re

def response(history_eng):
  
  template = """You are a helpful medical assistant. You are being provided with images,
  a question about the image and an answer. Follow the examples and answer the last question.
    <image>Question: What is/are the structure near/in the middle of the brain?
    Answer: pons.
    <|endofchunk|><image>Question: Is there evidence of a right apical pneumothorax on this chest x-ray?
      Answer: yes.
      <|endofchunk|><image>Question: Is/Are there air in the patient's peritoneal cavity?
      Answer: no.
      <|endofchunk|><image>Question: Does the heart appear enlarged?
      Answer: yes.
      <|endofchunk|><image>Question: What side are the infarcts located?
      Answer: bilateral.
      <|endofchunk|><image>Question: Which image modality is this?
      Answer: mr flair.
      {history}"""
  paths = image_paths[:6]
  new_paths = [ "/content/med-flamingo/" + path[3:]  for path in paths]
  new_paths.append(history_eng[0])
  images = [Image.open(path) for path in new_paths]
  question = f"<|endofchunk|><image>Question: {history_eng[1]}/n"
  model_input = template.format(history = question)
  pixels = processor.preprocess_images(images)
  pixels = repeat(pixels, 'N c h w -> b N T c h w', b=1, T=1)
  tokenized_data = processor.encode_text(model_input)

  print('Generate from multimodal few-shot prompt')
  with torch.autocast('cuda', torch.float16):
    generated_text = model.generate(
        vision_x=pixels.to(device),
        lang_x=tokenized_data["input_ids"].to(device),
        attention_mask=tokenized_data["attention_mask"].to(device),
        max_new_tokens=20,
    )
  response = processor.tokenizer.decode(generated_text[0])
  response = clean_generation(response)
  print("______________________check out this____________________________________")
  print(response)
  answers = re.findall(r"Answer: (.+)", response)
  # Get the last answer
  last_answer = answers[-1]
  return last_answer

  
eval_benchmark_dict = {}

def update_eval_benchmark(q_id, val1, val2, val3, val4):
  eval_benchmark_dict[q_id] = np.mean([val1, val2, val3, val4])
  print(q_id , eval_benchmark_dict[q_id])

def generate_response(question, image):
  if image :
    image.save("/content/output.jpg")
  else :
    Image.new("RGB", (800, 1280)).save("/content/output.jpg")
  query = ['/content/output.jpg', question]
  return response(query)

def next_question(old_id):
  return update_question(1, old_id)
def previous_question(old_id):
  return update_question(-1, old_id)

def generate_response_clinician(question, image):
  if image :
    query = [image, question]
  else :
    Image.new("RGB", (800, 1280)).save("/content/output.jpg")
    query = ['/content/output.jpg', question]
  return response(query),response(query),response(query),response(query)

def update_question(direction, old_id):
  id = int(old_id) + direction*1
  next_q = benchmark_dataset["question"][id]
  answer = benchmark_dataset["answer"][id]
  image = benchmark_dataset["image"][id]
  res1, res2, res3, res4 = generate_response(next_q, image), generate_response(next_q, image), generate_response(next_q, image), generate_response(next_q, image)
  return id, next_q, answer, image, res1, res2, res3, res4


with gr.Blocks(height = 300) as demo:
    gr.Markdown(
    """
    # Human Evaluation App
    A web app that allow clinical experts to evaluate the quality of the answers generated by SehhaTech
    """)
    with gr.Tab("Benchmark Datasets") as tab1:
        with gr.Row():
          with gr.Column(scale=1):
              id = np.random.randint(0, 300)
              q_id = gr.Textbox(label="Question ID", interactive=False, value=str(id) )
              q_text = gr.Textbox(label="Question", interactive=False, value=benchmark_dataset["question"][id])
              answer = gr.Textbox(label="Correct Answer", interactive=False, value=benchmark_dataset["answer"][id])
              q_img = gr.Image(benchmark_dataset["image"][id])
              with gr.Row():
                previous_btn = gr.Button("Previous")
                next_btn = gr.Button("Next")

          with gr.Column(scale=1):
              response1 = gr.Textbox(label="Response 1", interactive=False, value="Random1" )
              slider1 = gr.Slider(0, 10, step=1, label="Rating", )
              response2 = gr.Textbox(label="Response 2", interactive=False, value="Random2" )
              slider2 = gr.Slider(0, 10, step=1, label="Rating")
              response3 = gr.Textbox(label="Response 3", interactive=False, value="Random3" )
              slider3 = gr.Slider(0, 10, step=1, label="Rating")
              response4 = gr.Textbox(label="Response 4", interactive=False, value="Random4" )
              slider4 = gr.Slider(0, 10, step=1, label="Rating")
              slider1.release(update_eval_benchmark, [q_id, slider1, slider2, slider3, slider4])
              slider2.release(update_eval_benchmark, [q_id, slider1, slider2, slider3, slider4])
              slider3.release(update_eval_benchmark, [q_id, slider1, slider2, slider3, slider4])
              slider4.release(update_eval_benchmark, [q_id, slider1, slider2, slider3, slider4])
          next_btn.click(next_question, q_id, [q_id, q_text, answer, q_img, response1, response2, response3, response4])
          previous_btn.click(previous_question, q_id, [q_id, q_text, answer, q_img, response1, response2, response3, response4])
    with gr.Tab("Question by clinician"):
        with gr.Row():
          with gr.Column(scale=1):
              gr.Markdown("#### **Questions by expert**")
              q_text = gr.Textbox(label="Question", interactive=True, value="What is the disease")
              q_img = gr.Image(type = 'filepath')
              with gr.Row():
                generate_q = gr.Button("Generate Answer")

          with gr.Column(scale=1):
            gr.Markdown("#### **Generated Responses**")
            response1_ = gr.Textbox(label="Response 1", interactive=False, value="" )
            response2_ = gr.Textbox(label="Response 2", interactive=False, value="" )
            response3_ = gr.Textbox(label="Response 3", interactive=False, value="" )
            response4_ = gr.Textbox(label="Response 4", interactive=False, value="" )
            generate_q.click(generate_response_clinician, [q_text, q_img],[response1_,response2_,response3_,response4_, ])
          with gr.Column(scale=1):
            gr.Markdown("#### **Complete response evaluation**")
            correctness = gr.Slider(0, 1, step=0.25, label="Correctness", info="Average correctness of responses")
            harmlessness = gr.Slider(0, 10, step=1, label="Harmlessness", info = "(Are all the responses safe)")
            consistency = gr.Slider(0,10, step=1, label="Consistency", info ="Are responses similar")
            save_btn = gr.Button("Save Rating")
demo.launch(debug = True)