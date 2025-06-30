# SimpleQA Eval

SimpleQA: Measuring short-form factuality in large language models
Authors: Jason Wei, Nguyen Karina, Hyung Won Chung, Yunxin Joy Jiao, Spencer Papay, Amelia Glaese, John Schulman, William Fedus
https://cdn.openai.com/papers/simpleqa.pdf


Run instructions: 

```python
python experiments/eval/run.py --current-dir . --dataset SimpleQA --split main --run-id 0 --simulated-user-type none --parallel 1 --config experiments/endpoint_configs/config_template.yaml --mode run --system-type LLM
```

```
@article{wei2024measuring,
  title={Measuring short-form factuality in large language models},
  author={Wei, Jason and Karina, Nguyen and Chung, Hyung Won and Jiao, Yunxin Joy and Papay, Spencer and Glaese, Amelia and Schulman, John and Fedus, William},
  journal={arXiv preprint arXiv:2411.04368},
  year={2024}
}
```