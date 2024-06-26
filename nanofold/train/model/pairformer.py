from torch import nn
import torch

from nanofold.train.model.attention_pair_bias import AttentionPairBias
from nanofold.train.model.transition import Transition
from nanofold.train.model.triangular_attention import TriangleAttentionStartingNode
from nanofold.train.model.triangular_attention import TriangleAttentionEndingNode
from nanofold.train.model.triangular_update import TriangleMultiplicationOutgoing
from nanofold.train.model.triangular_update import TriangleMultiplicationIncoming
from nanofold.train.model.util import DropoutByDimension


class PairformerBlock(nn.Module):
    def __init__(
        self,
        single_embedding_size,
        pair_embedding_size,
        num_triangular_update_channels,
        num_triangular_attention_channels,
        num_triangular_attention_heads,
        num_pair_heads,
        transition_multiplier,
        p_dropout=0.25,
    ):
        super().__init__()
        self.pair_dropout = DropoutByDimension(p_dropout)
        self.triangle_update_outgoing = TriangleMultiplicationOutgoing(
            pair_embedding_size, num_triangular_update_channels
        )
        self.triangle_update_incoming = TriangleMultiplicationIncoming(
            pair_embedding_size, num_triangular_update_channels
        )
        self.triangle_attention_starting = TriangleAttentionStartingNode(
            pair_embedding_size, num_triangular_attention_heads, num_triangular_attention_channels
        )
        self.triangle_attention_ending = TriangleAttentionEndingNode(
            pair_embedding_size, num_triangular_attention_heads, num_triangular_attention_channels
        )
        self.pair_transition = Transition(pair_embedding_size, transition_multiplier)
        self.single_transition = Transition(single_embedding_size, transition_multiplier)
        self.attention_pair_bias = AttentionPairBias(
            num_pair_heads, single_embedding_size, 0, pair_embedding_size
        )

    def forward(self, single_rep, pair_rep):
        pair_rep = pair_rep + self.pair_dropout(self.triangle_update_outgoing(pair_rep), dim=-3)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_update_incoming(pair_rep), dim=-3)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_attention_starting(pair_rep), dim=-3)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_attention_ending(pair_rep), dim=-2)
        pair_rep = pair_rep + self.pair_transition(pair_rep)

        if single_rep is not None:
            single_rep = single_rep + self.attention_pair_bias(single_rep, None, pair_rep, None)
            single_rep = single_rep + self.single_transition(single_rep)
        return single_rep, pair_rep


class Pairformer(nn.Module):
    def __init__(
        self,
        single_embedding_size,
        pair_embedding_size,
        num_triangular_update_channels,
        num_triangular_attention_channels,
        num_triangular_attention_heads,
        num_pair_heads,
        transition_multiplier,
        num_blocks,
    ):
        super().__init__()
        self.blocks = nn.ModuleList(
            [
                PairformerBlock(
                    single_embedding_size,
                    pair_embedding_size,
                    num_triangular_update_channels,
                    num_triangular_attention_channels,
                    num_triangular_attention_heads,
                    num_pair_heads,
                    transition_multiplier,
                )
                for _ in range(num_blocks)
            ]
        )

    def forward(self, single_rep, pair_rep):
        for block in self.blocks:
            single_rep, pair_rep = block(single_rep, pair_rep)
        return single_rep, pair_rep
