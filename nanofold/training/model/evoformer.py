from torch import nn
import torch

from nanofold.training.model.msa_attention import MSAColumnAttention
from nanofold.training.model.msa_attention import MSARowAttentionWithPairBias
from nanofold.training.model.outer_product_mean import OuterProductMean
from nanofold.training.model.triangular_attention import TriangleAttentionStartingNode
from nanofold.training.model.triangular_attention import TriangleAttentionEndingNode
from nanofold.training.model.triangular_update import TriangleMultiplicationUpdate
from nanofold.training.model.triangular_update import UpdateDirection
from nanofold.training.model.util import DropoutByDimension


class EvoformerBlock(nn.Module):
    def __init__(
        self,
        pair_embedding_size,
        msa_embedding_size,
        triangular_update_embedding_size,
        triangular_attention_embedding_size,
        product_embedding_size,
        num_msa_heads,
        num_pair_heads,
        num_channels,
        transition_multiplier,
        p_msa_dropout=0.15,
        p_pair_dropout=0.25,
    ):
        super().__init__()
        self.msa_row_attention = MSARowAttentionWithPairBias(
            pair_embedding_size, msa_embedding_size, num_msa_heads, num_channels
        )
        self.msa_col_attention = MSAColumnAttention(msa_embedding_size, num_msa_heads, num_channels)
        self.msa_dropout = DropoutByDimension(p_msa_dropout)
        self.pair_dropout = DropoutByDimension(p_pair_dropout)
        self.msa_transition = nn.Sequential(
            nn.LayerNorm(msa_embedding_size),
            nn.Linear(msa_embedding_size, msa_embedding_size * transition_multiplier),
            nn.ReLU(),
            nn.Linear(msa_embedding_size * transition_multiplier, msa_embedding_size),
        )
        self.outer_product_mean = OuterProductMean(
            pair_embedding_size, msa_embedding_size, product_embedding_size
        )
        self.triangle_update_outgoing = TriangleMultiplicationUpdate(
            pair_embedding_size, triangular_update_embedding_size, UpdateDirection.OUTGOING
        )
        self.triangle_update_incoming = TriangleMultiplicationUpdate(
            pair_embedding_size, triangular_update_embedding_size, UpdateDirection.INCOMING
        )
        self.triangle_attention_starting = TriangleAttentionStartingNode(
            pair_embedding_size, triangular_attention_embedding_size, num_pair_heads
        )
        self.triangle_attention_ending = TriangleAttentionEndingNode(
            pair_embedding_size, triangular_attention_embedding_size, num_pair_heads
        )
        self.pair_transition = nn.Sequential(
            nn.LayerNorm(pair_embedding_size),
            nn.Linear(pair_embedding_size, pair_embedding_size * transition_multiplier),
            nn.ReLU(),
            nn.Linear(pair_embedding_size * transition_multiplier, pair_embedding_size),
        )

    def forward(self, msa_rep, pair_rep):
        msa_rep = msa_rep + self.msa_dropout(self.msa_row_attention(msa_rep, pair_rep), dim=-3)
        msa_rep = msa_rep + self.msa_col_attention(msa_rep)
        msa_rep = msa_rep + self.msa_transition(msa_rep)

        pair_rep = pair_rep + self.outer_product_mean(msa_rep)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_update_outgoing(pair_rep), dim=-3)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_update_incoming(pair_rep), dim=-3)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_attention_starting(pair_rep), dim=-3)
        pair_rep = pair_rep + self.pair_dropout(self.triangle_attention_ending(pair_rep), dim=-2)
        pair_rep = pair_rep + self.pair_transition(pair_rep)
        return msa_rep, pair_rep


class Evoformer(nn.Module):
    def __init__(
        self,
        single_embedding_size,
        pair_embedding_size,
        msa_embedding_size,
        triangular_update_embedding_size,
        triangular_attention_embedding_size,
        product_embedding_size,
        num_blocks,
        num_msa_heads,
        num_pair_heads,
        num_channels,
        evoformer_transition_multiplier,
    ):
        super().__init__()
        self.linear_single = nn.Linear(msa_embedding_size, single_embedding_size)
        self.blocks = nn.ModuleList(
            [
                EvoformerBlock(
                    pair_embedding_size,
                    msa_embedding_size,
                    triangular_update_embedding_size,
                    triangular_attention_embedding_size,
                    product_embedding_size,
                    num_msa_heads,
                    num_pair_heads,
                    num_channels,
                    evoformer_transition_multiplier,
                )
                for _ in range(num_blocks)
            ]
        )

    def forward(self, msa_rep, pair_rep):
        for block in self.blocks:
            msa_rep, pair_rep = block(msa_rep, pair_rep)

        single_rep = self.linear_single(msa_rep[..., 0, :, :])
        return single_rep
